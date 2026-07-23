import { useState, useEffect, useRef } from "react";
import { searchCompanies, listCompanies, ingestCompany, getCompany } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";

export default function HomePage({ onSelectCompany }) {
    const [query, setQuery] = useState("");
    const [searchResults, setSearchResults] = useState([]);
    const [savedCompanies, setSavedCompanies] = useState([]);
    const [ingesting, setIngesting] = useState({});
    const [error, setError] = useState(null);
    const [searched, setSearched] = useState(false);
    const pollingRefs = useRef({});

    // Load previously ingested companies on mount
    useEffect(() => {
        listCompanies()
            .then(r => setSavedCompanies(r.data))
            .catch(() => setError("Could not connect to backend — is it running?"));
    }, []);

    // Cleanup all polling intervals on unmount
    useEffect(() => {
        return () => {
            Object.values(pollingRefs.current).forEach(clearInterval);
        };
    }, []);

    const handleSearch = async () => {
        if (!query.trim()) return;
        try {
            const { data } = await searchCompanies(query);
            setSearchResults(data.results);
            setSearched(true);
            setError(null);
        } catch {
            setError("Search failed — is the backend running?");
        }
    };

    const handleIngest = async (ticker) => {
        setIngesting(prev => ({ ...prev, [ticker]: "running" }));
        try {
            await ingestCompany(ticker);

            // Clear any existing poll for this ticker
            if (pollingRefs.current[ticker]) {
                clearInterval(pollingRefs.current[ticker]);
            }

            pollingRefs.current[ticker] = setInterval(async () => {
                try {
                    const { data } = await getCompany(ticker);
                    if (data.ingestion_status === "done") {
                        clearInterval(pollingRefs.current[ticker]);
                        delete pollingRefs.current[ticker];
                        setIngesting(prev => ({ ...prev, [ticker]: "done" }));
                        const { data: companies } = await listCompanies();
                        setSavedCompanies(companies);
                        onSelectCompany(ticker);
                    } else if (data.ingestion_status === "failed") {
                        clearInterval(pollingRefs.current[ticker]);
                        delete pollingRefs.current[ticker];
                        setIngesting(prev => ({ ...prev, [ticker]: "failed" }));
                        setError(`Ingestion failed for ${ticker}`);
                    }
                } catch {}
            }, 4000);

        } catch {
            setIngesting(prev => ({ ...prev, [ticker]: "failed" }));
            setError(`Failed to start ingestion for ${ticker}`);
        }
    };

    return (
        <div className="min-h-screen bg-gray-50">
            <div className="max-w-3xl mx-auto px-4 py-16">

                {/* Header */}
                <h1 className="text-4xl font-bold text-gray-900 mb-2">
                    Stock Research Assistant
                </h1>
                <p className="text-gray-500 mb-10">
                    Ask natural language questions about any company — grounded in
                    their SEC filings, earnings calls, and news
                </p>

                {/* Search bar */}
                <div className="flex gap-2 mb-8">
                    <input
                        value={query}
                        onChange={e => setQuery(e.target.value)}
                        onKeyDown={e => e.key === "Enter" && handleSearch()}
                        placeholder="Search by company name or ticker (e.g. Apple, TSLA)..."
                        className="flex-1 border border-gray-300 rounded-lg px-4 py-3
                                   focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                        onClick={handleSearch}
                        className="bg-blue-600 text-white px-6 py-3 rounded-lg
                                   hover:bg-blue-700 font-medium transition-colors"
                    >
                        Search
                    </button>
                </div>

                {/* Error message */}
                {error && (
                    <p className="text-red-600 mb-4 text-sm">{error}</p>
                )}

                {/* Search results */}
                {searchResults.length > 0 && (
                    <div className="mb-8">
                        <h2 className="font-semibold text-gray-700 mb-3">
                            Search Results
                        </h2>
                        <div className="space-y-2">
                            {searchResults.map(r => (
                                <div key={r.ticker}
                                    className="bg-white border border-gray-200 rounded-lg
                                               p-4 flex items-center justify-between">
                                    <div>
                                        <span className="font-mono font-bold text-blue-700">
                                            {r.ticker}
                                        </span>
                                        <span className="ml-3 text-gray-700">{r.name}</span>
                                    </div>
                                    <button
                                        onClick={() => handleIngest(r.ticker)}
                                        disabled={ingesting[r.ticker] === "running"}
                                        className="bg-green-600 text-white px-4 py-2 rounded-lg
                                                   text-sm hover:bg-green-700 disabled:opacity-50
                                                   flex items-center gap-2 transition-colors"
                                    >
                                        {ingesting[r.ticker] === "running" ? (
                                            <>
                                                <LoadingSpinner size="sm" />
                                                Ingesting...
                                            </>
                                        ) : "Load & Research"}
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* No results */}
                {searched && searchResults.length === 0 && (
                    <p className="text-gray-500 mb-8">
                        No results found. Try a different name or ticker.
                    </p>
                )}

                {/* Previously ingested companies */}
                {savedCompanies.length > 0 && (
                    <div>
                        <h2 className="font-semibold text-gray-700 mb-3">
                            Your Companies
                        </h2>
                        <div className="space-y-2">
                            {savedCompanies.map(c => (
                                <div
                                    key={c.ticker}
                                    onClick={() => c.ingestion_status === "done" &&
                                        onSelectCompany(c.ticker)}
                                    className={`bg-white border border-gray-200 rounded-lg
                                               p-4 flex items-center justify-between
                                               ${c.ingestion_status === "done"
                                                   ? "cursor-pointer hover:border-blue-400 hover:shadow-sm transition-all"
                                                   : "opacity-70"}`}
                                >
                                    <div>
                                        <span className="font-mono font-bold text-gray-800">
                                            {c.ticker}
                                        </span>
                                        <span className="ml-3 text-gray-600">{c.name}</span>
                                        {c.sector && (
                                            <span className="ml-2 text-xs text-gray-400">
                                                · {c.sector}
                                            </span>
                                        )}
                                    </div>
                                    <StatusBadge status={c.ingestion_status} />
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Empty state */}
                {savedCompanies.length === 0 && !searched && (
                    <div className="text-center py-12 text-gray-400">
                        <p className="text-lg mb-2">No companies loaded yet</p>
                        <p className="text-sm">
                            Search for a company above to get started
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}