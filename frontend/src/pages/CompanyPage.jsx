import { useState, useEffect, useRef } from "react";
import { getCompany, getHistory, getSuggestions } from "../api/client";
import { askStream } from "../api/client";
import FilterBar from "../components/FilterBar";
import AnswerPanel from "../components/AnswerPanel";
import LoadingSpinner from "../components/LoadingSpinner";

export default function CompanyPage({ ticker, onBack }) {
    const [company, setCompany] = useState(null);
    const [question, setQuestion] = useState("");
    const [streamingText, setStreamingText] = useState("");
    const [currentSources, setCurrentSources] = useState([]);
    const [isStreaming, setIsStreaming] = useState(false);
    const [docType, setDocType] = useState(null);
    const [history, setHistory] = useState([]);
    const [suggestions, setSuggestions] = useState([]);
    const [showAnswer, setShowAnswer] = useState(false);
    const answerRef = useRef(null);

    useEffect(() => {
        getCompany(ticker).then(r => setCompany(r.data));
        getHistory(ticker).then(r => setHistory(r.data));
        getSuggestions(ticker).then(r => setSuggestions(r.data.questions));
    }, [ticker]);

    const handleAsk = async (q = question) => {
        if (!q.trim() || isStreaming) return;
        setIsStreaming(true);
        setStreamingText("");
        setCurrentSources([]);
        setShowAnswer(true);

        try {
            const response = await askStream(ticker, q, docType);
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullText = "";
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop();

                for (const line of lines) {
                    if (line.startsWith("event: sources")) continue;
                    if (line.startsWith("event: done")) continue;
                    if (!line.startsWith("data: ")) continue;

                    const raw = line.slice(6).trim();
                    if (!raw) continue;

                    try {
                        const parsed = JSON.parse(raw);
                        if (Array.isArray(parsed)) {
                            setCurrentSources(parsed);
                        } else if (parsed.token) {
                            fullText += parsed.token;
                            setStreamingText(fullText);
                        } else if (parsed.full_answer) {
                            setStreamingText(parsed.full_answer);
                        }
                    } catch {}
                }
            }

            getHistory(ticker).then(r => setHistory(r.data));
            setTimeout(() => {
                answerRef.current?.scrollIntoView({ behavior: "smooth" });
            }, 100);

        } catch (err) {
            setStreamingText(`Error: ${err.message}`);
        } finally {
            setIsStreaming(false);
        }
    };

    if (!company) {
        return (
            <div className="flex justify-center items-center min-h-screen">
                <LoadingSpinner size="lg" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50">
            <div className="max-w-4xl mx-auto px-4 py-8">

                {/* Header */}
                <div className="flex items-center gap-4 mb-8">
                    <button
                        onClick={onBack}
                        className="text-blue-600 hover:underline text-sm"
                    >
                        ← Back
                    </button>
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">
                            {company.name}
                        </h1>
                        <span className="text-gray-500 font-mono text-sm">
                            {ticker}
                            {company.sector && ` · ${company.sector}`}
                        </span>
                    </div>
                </div>

                {/* Filter bar */}
                <FilterBar selected={docType} onChange={setDocType} />

                {/* Question input */}
                <div className="bg-white border border-gray-200 rounded-xl p-4 mb-6">
                    <textarea
                        value={question}
                        onChange={e => setQuestion(e.target.value)}
                        onKeyDown={e => {
                            if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                handleAsk();
                            }
                        }}
                        placeholder="Ask anything about this company... (Enter to send)"
                        rows={2}
                        className="w-full resize-none focus:outline-none text-gray-800
                                   placeholder-gray-400"
                    />
                    <div className="flex justify-between items-center mt-2">
                        <span className="text-xs text-gray-400">
                            Shift+Enter for new line
                        </span>
                        <button
                            onClick={() => handleAsk()}
                            disabled={isStreaming || !question.trim()}
                            className="bg-blue-600 text-white px-6 py-2 rounded-lg
                                       hover:bg-blue-700 disabled:opacity-50
                                       flex items-center gap-2 transition-colors"
                        >
                            {isStreaming ? (
                                <><LoadingSpinner size="sm" /> Thinking...</>
                            ) : "Ask"}
                        </button>
                    </div>
                </div>

                {/* Suggested questions */}
                {!showAnswer && suggestions.length > 0 && (
                    <div className="mb-6">
                        <p className="text-sm text-gray-500 mb-2">Try asking:</p>
                        <div className="flex flex-wrap gap-2">
                            {suggestions.map((s, i) => (
                                <button
                                    key={i}
                                    onClick={() => {
                                        setQuestion(s);
                                        handleAsk(s);
                                    }}
                                    className="text-sm bg-white border border-gray-200
                                               rounded-full px-4 py-2 hover:border-blue-400
                                               hover:text-blue-600 transition-colors text-gray-600"
                                >
                                    {s}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Answer panel */}
                {showAnswer && (
                    <div ref={answerRef}>
                        <AnswerPanel
                            answer={streamingText}
                            sources={currentSources}
                            isStreaming={isStreaming}
                        />
                    </div>
                )}

                {/* Question history */}
                {history.length > 0 && (
                    <div className="mt-6">
                        <h3 className="font-semibold text-gray-700 mb-3">
                            Previous Questions
                        </h3>
                        <div className="space-y-2">
                            {history.map((h, i) => (
                                <div
                                    key={h.id || i}
                                    onClick={() => {
                                        setStreamingText(h.answer);
                                        setCurrentSources(h.sources || []);
                                        setShowAnswer(true);
                                    }}
                                    className="bg-white border border-gray-200 rounded-lg
                                               p-3 cursor-pointer hover:border-blue-300
                                               transition-colors"
                                >
                                    <p className="text-sm font-medium text-gray-800">
                                        {h.question}
                                    </p>
                                    <p className="text-xs text-gray-400 mt-1">
                                        {h.asked_at?.slice(0, 10)}
                                    </p>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}