import { useState, FormEvent, KeyboardEvent } from 'react';
import { Search, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';

interface SearchBoxProps {
    onSearch: (query: string) => void;
    isLoading?: boolean;
    placeholder?: string;
}

export function SearchBox({
    onSearch,
    isLoading = false,
    placeholder = '描述你想找的图片...'
}: SearchBoxProps) {
    const [query, setQuery] = useState('');

    const handleSubmit = (e: FormEvent) => {
        e.preventDefault();
        if (query.trim() && !isLoading) {
            onSearch(query.trim());
        }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    };

    return (
        <motion.form
            onSubmit={handleSubmit}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="w-full max-w-2xl mx-auto"
        >
            <div className="glass relative rounded-2xl p-1 transition-all duration-300 hover:shadow-lg focus-within:shadow-xl focus-within:shadow-indigo-500/20">
                <div className="flex items-center gap-3 bg-white/5 rounded-xl px-4 py-3">
                    <Sparkles className="text-indigo-400 flex-shrink-0" size={20} />
                    <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={placeholder}
                        disabled={isLoading}
                        className="flex-1 bg-transparent text-white placeholder-gray-400 outline-none text-base"
                    />
                    <button
                        type="submit"
                        disabled={!query.trim() || isLoading}
                        className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-500 text-white transition-all duration-300 hover:scale-105 hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                    >
                        {isLoading ? (
                            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        ) : (
                            <Search size={18} />
                        )}
                    </button>
                </div>
            </div>
        </motion.form>
    );
}
