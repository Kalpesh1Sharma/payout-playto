import React, { useCallback, useEffect, useState } from "react";

import { createPayout, getMerchantLedger, getMerchants, getPayouts } from "./api";
import Dashboard from "./components/Dashboard";

const formatINR = (paise) =>
  `Rs ${(paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
const formatDate = (iso) =>
  new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });

export default function App() {
  const [merchants, setMerchants] = useState([]);
  const [selectedMerchant, setSelectedMerchant] = useState(null);
  const [ledger, setLedger] = useState(null);
  const [payouts, setPayouts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [payoutForm, setPayoutForm] = useState({ amount: "", error: "", success: "" });

  useEffect(() => {
    getMerchants().then((r) => {
      setMerchants(r.data);
      if (r.data.length > 0) setSelectedMerchant(r.data[0]);
    });
  }, []);

  const fetchData = useCallback(async () => {
    if (!selectedMerchant) return;
    const [ledgerRes, payoutsRes] = await Promise.all([
      getMerchantLedger(selectedMerchant.id),
      getPayouts(selectedMerchant.id),
    ]);
    setLedger(ledgerRes.data);
    setPayouts(payoutsRes.data);
  }, [selectedMerchant]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handlePayout = async () => {
    const amountPaise = Math.round(parseFloat(payoutForm.amount) * 100);
    if (!amountPaise || amountPaise < 100) {
      setPayoutForm((f) => ({ ...f, error: "Minimum payout is Rs 1" }));
      return;
    }
    const bankAccountId = selectedMerchant.bank_accounts[0]?.id;
    if (!bankAccountId) {
      setPayoutForm((f) => ({ ...f, error: "No bank account found" }));
      return;
    }

    const idempotencyKey = crypto.randomUUID();
    setLoading(true);
    setPayoutForm((f) => ({ ...f, error: "", success: "" }));
    try {
      await createPayout(selectedMerchant.id, amountPaise, bankAccountId, idempotencyKey);
      setPayoutForm({ amount: "", error: "", success: "Payout requested!" });
      fetchData();
    } catch (e) {
      const msg = e.response?.data?.error || "Request failed";
      setPayoutForm((f) => ({ ...f, error: msg }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0b] text-[#e8e8e8]">
      <header className="border-b border-white/5 px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded bg-emerald-500 flex items-center justify-center text-xs font-bold text-black">
            P
          </div>
          <span className="font-semibold text-white tracking-tight">Playto Pay</span>
          <span className="text-white/20 text-sm">|</span>
          <span className="text-white/40 text-sm">Merchant Dashboard</span>
        </div>
        <div className="text-xs text-white/20 font-mono">live</div>
      </header>

      <div className="max-w-6xl mx-auto px-8 py-8">
        <div className="flex gap-2 mb-8">
          {merchants.map((m) => (
            <button
              key={m.id}
              onClick={() => setSelectedMerchant(m)}
              className={`px-4 py-2 rounded-lg text-sm transition-all ${
                selectedMerchant?.id === m.id
                  ? "bg-white/10 text-white border border-white/20"
                  : "text-white/40 hover:text-white/70 hover:bg-white/5"
              }`}
            >
              {m.name}
            </button>
          ))}
        </div>

        {selectedMerchant && ledger && (
          <Dashboard
            ledger={ledger}
            payouts={payouts}
            selectedMerchant={selectedMerchant}
            payoutForm={payoutForm}
            setPayoutForm={setPayoutForm}
            loading={loading}
            onSubmitPayout={handlePayout}
            formatDate={formatDate}
            formatINR={formatINR}
          />
        )}
      </div>
    </div>
  );
}
