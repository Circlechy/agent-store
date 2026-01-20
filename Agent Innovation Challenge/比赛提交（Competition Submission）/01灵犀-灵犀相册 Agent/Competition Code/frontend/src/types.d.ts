declare module 'lucide-react' {
    import { ComponentType, SVGProps } from 'react';

    export interface IconProps extends SVGProps<SVGSVGElement> {
        size?: number | string;
        strokeWidth?: number | string;
        absoluteStrokeWidth?: boolean;
    }

    export type Icon = ComponentType<IconProps>;

    export const Loader2: Icon;
    export const ImageOff: Icon;
    export const Search: Icon;
    export const Sparkles: Icon;
    export const Send: Icon;
    export const User: Icon;
    export const Bot: Icon;
    export const Camera: Icon;
    export const Image: Icon;
    export const ArrowLeft: Icon;
    export const Trash2: Icon;
}

declare module 'react-masonry-css' {
    import { ComponentType, ReactNode } from 'react';

    interface MasonryProps {
        breakpointCols?: number | { [key: number]: number; default: number };
        className?: string;
        columnClassName?: string;
        children?: ReactNode;
    }

    const Masonry: ComponentType<MasonryProps>;
    export default Masonry;
}

declare module 'yet-another-react-lightbox' {
    import { ComponentType } from 'react';

    interface Slide {
        src: string;
        alt?: string;
        title?: string;
    }

    interface LightboxProps {
        open: boolean;
        close: () => void;
        index?: number;
        slides: Slide[];
        on?: {
            view?: (params: { index: number }) => void;
        };
        styles?: {
            container?: React.CSSProperties;
        };
    }

    const Lightbox: ComponentType<LightboxProps>;
    export default Lightbox;
}

declare module 'yet-another-react-lightbox/styles.css';
