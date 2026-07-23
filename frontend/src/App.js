import { useState } from "react";
import HomePage from "./pages/HomePage";
import CompanyPage from "./pages/CompanyPage";

export default function App() {
    const [currentTicker, setCurrentTicker] = useState(null);

    return (
        <div className="min-h-screen bg-gray-50 font-sans">
            {currentTicker
                ? <CompanyPage
                    ticker={currentTicker}
                    onBack={() => setCurrentTicker(null)}
                  />
                : <HomePage
                    onSelectCompany={setCurrentTicker}
                  />
            }
        </div>
    );
}