// src/components/utils/HTMLRenderer.js
import React from 'react';

/**
 * A helper component to safely render HTML strings
 * Uses dangerouslySetInnerHTML to render HTML tags like <strong>, <span>, etc.
 * 
 * @param {string} content - The HTML string to render
 * @param {object} style - Optional style object to apply to the container
 * @param {string} className - Optional className to apply to the container
 */
export default function HTMLRenderer({ content, style, className, tag = 'div' }) {
  if (!content) return null;
  
  // If content doesn't contain HTML tags, render as plain text
  // This avoids unnecessary use of dangerouslySetInnerHTML
  if (typeof content !== 'string' || !/<[^>]+>/.test(content)) {
    const Tag = tag;
    return <Tag style={style} className={className}>{content}</Tag>;
  }
  
  const Tag = tag;
  return (
    <Tag
      style={style}
      className={className}
      dangerouslySetInnerHTML={{ __html: content }}
    />
  );
}


