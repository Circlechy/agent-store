import { useState, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Search } from 'lucide-react';
import type { ImageResult } from '../../api/types';

interface ImageCardProps {
    image: ImageResult;
    onClick?: () => void;
    index?: number;
}

export function ImageCard({ image, onClick, index = 0 }: ImageCardProps) {
    const [isLoaded, setIsLoaded] = useState(false);
    const [isInView, setIsInView] = useState(false);
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting) {
                    setIsInView(true);
                    observer.disconnect();
                }
            },
            { rootMargin: '100px' }
        );

        if (ref.current) observer.observe(ref.current);
        return () => observer.disconnect();
    }, []);

    const imageUrl = image.preview_url || `http://localhost:8000/api/v1/storage/files/${image.metadata.file_path}`;
    const matchScore = Math.round(image.score * 100);

    return (
        <motion.div
            ref={ref}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            whileHover={{ y: -6 }}
            transition={{ duration: 0.3 }}
            onClick={onClick}
            className="image-card cursor-pointer group"
        >
            <div className="relative overflow-hidden rounded-xl bg-background-secondary dark:bg-background-secondary">
                {/* Skeleton */}
                {!isLoaded && (
                    <div className="absolute inset-0 skeleton" />
                )}

                {/* Image */}
                {isInView && (
                    <img
                        src={imageUrl}
                        alt={image.metadata.filename}
                        onLoad={() => setIsLoaded(true)}
                        className={`w-full h-auto object-cover transition-all duration-500 ${isLoaded ? 'opacity-100 scale-100' : 'opacity-0 scale-105'
                            }`}
                        style={{ aspectRatio: 'auto' }}
                    />
                )}

                {/* Overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                    {/* Bottom Info - 增强间距 */}
                    <div className="absolute bottom-0 left-0 right-0 p-5">
                        <p className="text-white text-sm font-medium truncate mb-3">
                            {image.metadata.filename}
                        </p>
                        <div className="flex items-center gap-2.5 flex-wrap">
                            {matchScore < 100 && (
                                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-primary text-white">
                                    {matchScore}% 匹配
                                </span>
                            )}
                            {image.metadata.tags && image.metadata.tags.length > 0 && (
                                <div className="flex gap-1.5">
                                    {image.metadata.tags.slice(0, 3).map((tag, i) => (
                                        <span key={i} className="px-2.5 py-1 rounded-full text-xs bg-white/20 text-white backdrop-blur-sm">
                                            {tag}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Center View Icon */}
                    <div className="absolute inset-0 flex items-center justify-center">
                        <motion.div
                            initial={{ scale: 0.8, opacity: 0 }}
                            whileHover={{ scale: 1, opacity: 1 }}
                            className="w-16 h-16 rounded-full bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center"
                        >
                            <Search className="text-white" size={26} />
                        </motion.div>
                    </div>
                </div>
            </div>
        </motion.div>
    );
}
