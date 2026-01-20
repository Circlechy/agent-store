import numpy as np
from PIL import Image
import math
import os
import torch
import torch.nn.functional as F
import torchvision.transforms.functional as TF
import cv2
from decord import VideoReader
from transformers import CLIPImageProcessor

SHORT_SIDE = 720  # 图片resize后短边像素度
OPTICAL_FLOW_THRESHOLD = 1.0  # 光流选帧阈值
OPTICAL_FLOW_DEVICE = 'cuda:0'  # 光流选帧计算GPU

def uniform_sampling(vr, video_fps):
    sample_fps = round(vr.get_avg_fps() / video_fps)
    frame_idx = [i for i in range(0, len(vr), sample_fps)]
    video = vr.get_batch(frame_idx).asnumpy()
    return video

last_frame = None
def optical_flow_keyframe_sampling(frames, optical_flow_threshold: float = OPTICAL_FLOW_THRESHOLD, device: str = OPTICAL_FLOW_DEVICE):
    image_processor = CLIPImageProcessor()
    global last_frame
    selected_frames = []
    for frame in frames:
        current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if last_frame is None:
            last_frame = current_frame
            continue
        with torch.no_grad():
            is_change, _, _ = calculate_optical_flow(last_frame, current_frame, image_processor, optical_flow_threshold, device)
        torch.cuda.empty_cache()
        last_frame = current_frame
        if is_change:
            selected_frames.append(frame)
    selected_frames = np.array(selected_frames)
    return selected_frames

prev_img = None
def pixel_differential_keyframe_sampling(
        frames: np.ndarray,  # shape: (T, H, W, 3)
        patch_size: int = 14,
        token_drop_threshold: float = 0.1,
        drop_ratio_threshold: float = 0.7,
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
) -> np.ndarray:
    def should_keep_frame(
            prev_frame: Image.Image,
            curr_frame: Image.Image,
            patch_size: int = 14,
            token_drop_threshold: float = 0.1,
            drop_ratio_threshold: float = 0.7,
            device: torch.device = torch.device("cpu")
    ) -> tuple[bool, float]:
        prev_tensor = TF.to_tensor(prev_frame).unsqueeze(0).to(device)
        curr_tensor = TF.to_tensor(curr_frame).unsqueeze(0).to(device)

        _, _, H, W = prev_tensor.shape
        H_crop, W_crop = H - H % patch_size, W - W % patch_size
        prev_tensor = prev_tensor[:, :, :H_crop, :W_crop]
        curr_tensor = curr_tensor[:, :, :H_crop, :W_crop]

        prev_patches = F.unfold(prev_tensor, kernel_size=patch_size, stride=patch_size)
        curr_patches = F.unfold(curr_tensor, kernel_size=patch_size, stride=patch_size)

        diff = torch.abs(prev_patches - curr_patches).mean(dim=1)
        low_diff_ratio = (diff < token_drop_threshold).float().mean().item()
        keep = low_diff_ratio < drop_ratio_threshold
        return keep, low_diff_ratio

    selected_frames = []
    global prev_img
    device = torch.device(device)

    for idx in range(frames.shape[0]):
        curr_img = Image.fromarray(frames[idx])  # Convert from ndarray to PIL.Image

        if prev_img is None:
            selected_frames.append(curr_img)
            prev_img = curr_img
            print(f"[Frame {idx}] First frame kept.")
        else:
            keep, ratio = should_keep_frame(
                prev_img, curr_img,
                patch_size=patch_size,
                token_drop_threshold=token_drop_threshold,
                drop_ratio_threshold=drop_ratio_threshold,
                device=device
            )
            if keep:
                selected_frames.append(curr_img)
                prev_img = curr_img
                print(f"[Frame {idx}] Kept (low-diff ratio: {ratio:.4f})")
            else:
                print(f"[Frame {idx}] Dropped (low-diff ratio: {ratio:.4f})")

    print("\n=== In-Memory Selection Summary ===")
    print(f"Input frames: {len(frames)}")
    print(f"Kept frames:  {len(selected_frames)}")
    print(f"Kept ratio:   {len(selected_frames) / len(frames):.2%}")

    selected_array = np.stack([np.array(f) for f in selected_frames])
    return selected_array


def ndarray_image_resolution_resize(
        image: np.ndarray,  # shape: (H, W, 3)
        short_side: int = SHORT_SIDE
) -> np.ndarray:
    """
    保持原始图片横纵比的基础上，对图片进行resize
    输入参数：
        image: 三维numpy数组 (H, W, 3)
        short_side: 目标短边像素值

    1. 保持原图比例，将短边缩放到指定像素值
    2. 长边按原始比例自动计算
    3. 返回与输入类型相同的ndarray

    异常处理：
    - 输入不是ndarray或维度不符 → 返回原图
    - short_side <= 0 → 返回原图
    """

    # 获取原始尺寸
    H, W = image.shape[:2]
    src_short, src_long = min(H, W), max(H, W)
    is_height_short = H < W  # 标志高度是否为短边

    # 计算新尺寸 (保持比例)
    scale_factor = short_side / src_short
    new_long = int(round(src_long * scale_factor))

    # 确定新尺寸（短边在前，保持原始方向）
    new_size = (short_side, new_long) if is_height_short else (new_long, short_side)

    # 转换并resize
    pil_img = Image.fromarray(image)
    resized_img = pil_img.resize(new_size[::-1])  # PIL需要(width, height)
    return np.array(resized_img)

def calculate_optical_flow(last_frame, current_frame, image_processor, threshold, device):
    window_size, eps = 5, 1e-6
    assert last_frame is not None
    current_image_tensor = process_images([Image.fromarray(current_frame)], image_processor).to(device).squeeze(0)
    last_image_tensor = process_images([Image.fromarray(last_frame)], image_processor).to(device).squeeze(0)
    if current_image_tensor.dim() == 3:
        current_image_tensor_gray = 0.2989 * current_image_tensor[0, :, :] + 0.5870 * current_image_tensor[1, :, :] + 0.1140 * current_image_tensor[2, :, :]
        last_image_tensor_gray = 0.2989 * last_image_tensor[0, :, :] + 0.5870 * last_image_tensor[1, :, :] + 0.1140 * last_image_tensor[2, :, :]
    else:
        current_image_tensor_gray = current_image_tensor
        last_image_tensor_gray = last_image_tensor

    # Compute gradients on GPU
    Ix, Iy = compute_gradients(last_image_tensor_gray.unsqueeze(0))
    It = current_image_tensor_gray - last_image_tensor_gray

    # Prepare for batch processing
    Ix_windows = F.unfold(Ix.unsqueeze(0), kernel_size=(window_size, window_size)).transpose(1, 2)
    Iy_windows = F.unfold(Iy.unsqueeze(0), kernel_size=(window_size, window_size)).transpose(1, 2)
    It_windows = F.unfold(It.unsqueeze(0).unsqueeze(0), kernel_size=(window_size, window_size)).transpose(1, 2)
    A = torch.stack((Ix_windows, Iy_windows), dim=3)
    b = -It_windows

    # Using Lucas-Karthy method
    # Reshape to (batch_size, num_windows, window_size*window_size, 2)
    A = A.view(A.size(0), -1, window_size*window_size, 2)
    b = b.view(b.size(0), -1, window_size*window_size)

    # Compute A^T * A and A^T * b
    A_T_A = torch.matmul(A.transpose(2, 3), A)
    A_T_b = torch.matmul(A.transpose(2, 3), b.unsqueeze(3)).squeeze(3)

    # Add regularization term to A_T_A
    eye = torch.eye(A_T_A.size(-1), device=A_T_A.device)
    A_T_A += eps * eye

    # Solve for flow vectors in batch
    nu = torch.linalg.solve(A_T_A, A_T_b)

    u_flat = nu[:, :, 0]
    v_flat = nu[:, :, 1]

    # Reshape flow vectors to image shape
    # Calculate correct output size for fold
    output_height = Ix.shape[1] - window_size + 1
    output_width = Ix.shape[2] - window_size + 1

    # Ensure the data is suitable for fold operation
    u_flat = u_flat.view(1, output_height,  output_width)
    v_flat = v_flat.view(1, output_height,  output_width)

    # Compute magnitude of flow vectors
    mag = torch.sqrt(u_flat**2 + u_flat**2)
    mean_mag = mag.mean().item()

    del Ix_windows, Iy_windows, It_windows
    del current_image_tensor_gray, last_image_tensor_gray, last_image_tensor

    return mean_mag > threshold, mean_mag, current_image_tensor

def process_images(images, image_processor):
    new_images = []
    for image in images:
        image = image_processor.preprocess(image, return_tensors="pt")["pixel_values"][0]
        new_images.append(image) # [ dim resize_w resize_h ]
    if len(images) > 1:
        new_images = [torch.stack(new_images, dim=0)] # [num_images dim resize_w resize_h ]
    if all(x.shape == new_images[0].shape for x in new_images):
        new_images = torch.stack(new_images, dim=0) # num_image num_patches dim resize_w resize_h
        # when using "pad" mode and only have one image the new_images tensor dimension is [ 1 dim resize_w resize_h ]
    return new_images

def compute_gradients(img):
    sobel_x = torch.tensor([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=torch.float32, device=img.device).unsqueeze(0).unsqueeze(0)
    sobel_y = torch.tensor([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=torch.float32, device=img.device).unsqueeze(0).unsqueeze(0)
    Ix = F.conv2d(img.unsqueeze(0), sobel_x, padding=1)
    Iy = F.conv2d(img.unsqueeze(0), sobel_y, padding=1)
    return Ix.squeeze(0), Iy.squeeze(0)

if __name__ == '__main__':

    # 构造指定fps帧序列
    video_paths = [
        'data/d4f7470e-9f09-43c6-a29d-6722f0656886.mp4',
        'data/39f9a8a9-9979-475b-b4f9-1fa2eda064a4.mp4',
        'data/3a1a5a27-7ac3-4323-8345-6717c175b09b.mp4',
        'data/2276090d-3aab-4a4f-afbe-dcc083604160.mp4',
        'data/ba265640-5261-4e3f-9b52-dda27d34898a.mp4',
    ]
    video_fps = 1
    for index, video_path in enumerate(video_paths):
        vr = VideoReader(video_path)
        frames = uniform_sampling(vr, video_fps)

        # 智能光流选帧
        device = "cuda" if torch.cuda.is_available() else "cpu"
        selected_frames = optical_flow_keyframe_sampling(frames)
        print(f'original_frames_cnt: {len(frames)}, sampled_frame_cnt: {len(selected_frames)}, droping_rate: {(1 - len(selected_frames)/len(frames)):.4f}')

        # # 对比选帧结果
        # output_dir = 'data/tmp'
        # original = os.path.join(output_dir, 'original')
        # selected = os.path.join(output_dir, 'selected')
        # if not os.path.exists(original):
        #     os.makedirs(original)
        # if not os.path.exists(selected):
        #     os.makedirs(selected)
        # for i, frame in enumerate(frames):
        #     cv2.imwrite(os.path.join(original, f'{index}_{i}.png'), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        # for i, selected_frame in enumerate(selected_frames):
        #     cv2.imwrite(os.path.join(selected, f'{index}_{i}.png'), cv2.cvtColor(selected_frame, cv2.COLOR_RGB2BGR))
