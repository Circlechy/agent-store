import React, { useState, useEffect } from 'react';

export interface TypewriterPart {
  text: string;
  style?: React.CSSProperties;
  className?: string;
}

interface TypewriterEffectProps {
  parts: TypewriterPart[];
  speed?: number;
  cursorColor?: string;
  style?: React.CSSProperties;
  className?: string;
}

export const TypewriterEffect: React.FC<TypewriterEffectProps> = ({
  parts,
  speed = 50,
  cursorColor = '#1677ff',
  style,
  className,
}) => {
  const [currentLength, setCurrentLength] = useState(0);
  const [isTyping, setIsTyping] = useState(true);

  // Calculate total length
  const totalLength = parts.reduce((acc, part) => acc + part.text.length, 0);

  useEffect(() => {
    setCurrentLength(0);
    setIsTyping(true);

    const intervalId = setInterval(() => {
      setCurrentLength((prev) => {
        if (prev < totalLength) {
          return prev + 1;
        } else {
          clearInterval(intervalId);
          setIsTyping(false);
          return prev;
        }
      });
    }, speed);

    return () => clearInterval(intervalId);
  }, [totalLength, speed]);

  // Render parts based on currentLength
  const renderContent = () => {
    let remainingChars = currentLength;
    
    return parts.map((part, index) => {
      if (remainingChars <= 0) {
        return null;
      }
      
      const charCount = Math.min(remainingChars, part.text.length);
      const displayText = part.text.slice(0, charCount);
      remainingChars -= charCount;
      
      return (
        <span key={index} style={part.style} className={part.className}>
          {displayText}
        </span>
      );
    });
  };

  return (
    <span style={style} className={className}>
      {renderContent()}
      <span
        style={{
          display: 'inline-block',
          width: '0.1em',
          height: '1em',
          backgroundColor: cursorColor,
          marginLeft: '2px',
          verticalAlign: 'text-bottom',
          animation: 'blink 1s step-end infinite',
          opacity: isTyping ? 1 : 0.5,
        }}
      />
      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </span>
  );
};
