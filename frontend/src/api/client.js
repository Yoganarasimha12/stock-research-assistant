import axios from "axios";

const API = axios.create({
    baseURL: process.env.REACT_APP_API_URL || "http://localhost:8000",
    timeout: 60000,
});

// Companies
export const searchCompanies = (q) =>
    API.get(`/companies/search?q=${encodeURIComponent(q)}`);

export const getCompany = (ticker) =>
    API.get(`/companies/${ticker}`);

export const listCompanies = () =>
    API.get("/companies/");

export const ingestCompany = (ticker, force = false) =>
    API.post(`/companies/${ticker}/ingest?force=${force}`);

export const getDocuments = (ticker, docType) =>
    API.get(`/companies/${ticker}/documents${docType ? `?doc_type=${docType}` : ""}`);

// Prices
export const getPrices = (ticker, period = "1y") =>
    API.get(`/companies/${ticker}/prices?period=${period}`);

export const getCompanyInfo = (ticker) =>
    API.get(`/companies/${ticker}/info`);

// Questions
export const askQuestion = (ticker, question, docType) =>
    API.post(`/companies/${ticker}/ask`, {
        question,
        doc_type: docType || null
    });

export const getHistory = (ticker) =>
    API.get(`/companies/${ticker}/questions`);

export const getSuggestions = (ticker) =>
    API.get(`/companies/${ticker}/suggestions`);

// Streaming — returns raw fetch Response for manual reading
export const askStream = (ticker, question, docType) =>
    fetch(
        `${process.env.REACT_APP_API_URL || "http://localhost:8000"}/companies/${ticker}/ask/stream`,
        {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question,
                doc_type: docType || null
            }),
        }
    );