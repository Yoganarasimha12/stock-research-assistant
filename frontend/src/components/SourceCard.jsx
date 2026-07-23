import { useState } from "react";

export default function SourceCard({ source }) {
    const [expanded, setExpanded] = useState(false);

    const typeColors = {
        "10-K": "bg-blue-100 text-blue-700",
        "10-Q": "bg-purple-100 text-purple-700",
        "news": "bg-orange-100 text-orange-700",
    };

    return (
        <div
            id={`source-${source.rank}`}
            className="border border-gray-200 rounded-lg p-3 cursor-pointer
                       hover:bg-gray-50 transition-colors"
            onClick={() => setExpanded(!expanded)}
        >
            <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-gray-400">
                    [{source.rank}]
                </span>
                <span className={`text-xs px-2 py-0.5 rounded font-medium
                    ${typeColors[source.doc_type] || "bg-gray-100 text-gray-600"}`}>
                    {source.doc_type}
                </span>
                <span className="text-xs text-gray-400">{source.date}</span>
                <span className="ml-auto text-xs text-gray-400">
                    {expanded ? "▲ hide" : "▼ show"}
                </span>
            </div>

            {expanded && (
                <div className="mt-2 text-xs text-gray-700 bg-gray-50
                                rounded p-3 leading-relaxed">
                    {source.chunk_text}
                    {source.url && (
                        <a
                            href={source.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-blue-600 block mt-2 hover:underline"
                            onClick={e => e.stopPropagation()}
                        >
                            View original document →
                        </a>
                    )}
                </div>
            )}
        </div>
    );
}