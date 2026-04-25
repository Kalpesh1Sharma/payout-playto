export default function PayoutForm({
  selectedMerchant,
  payoutForm,
  setPayoutForm,
  loading,
  onSubmit,
}) {
  return (
    <>
      <h2 className="text-sm font-medium text-white/60 uppercase tracking-widest mb-4">
        Request Payout
      </h2>
      <div className="bg-white/3 border border-white/8 rounded-xl p-6">
        <div className="mb-4">
          <label className="block text-xs text-white/40 mb-2">Amount (INR)</label>
          <div className="flex items-center border border-white/10 rounded-lg bg-white/5 px-4 py-3">
            <span className="text-white/40 mr-2">Rs</span>
            <input
              type="number"
              className="bg-transparent flex-1 outline-none text-white font-mono"
              placeholder="0.00"
              value={payoutForm.amount}
              onChange={(e) => setPayoutForm((f) => ({ ...f, amount: e.target.value }))}
            />
          </div>
        </div>
        <div className="text-xs text-white/30 mb-4">
          To: {selectedMerchant.bank_accounts[0]?.account_number || "No account"} ·{" "}
          {selectedMerchant.bank_accounts[0]?.ifsc_code}
        </div>
        {payoutForm.error && <div className="text-red-400 text-xs mb-3">{payoutForm.error}</div>}
        {payoutForm.success && (
          <div className="text-emerald-400 text-xs mb-3">{payoutForm.success}</div>
        )}
        <button
          onClick={onSubmit}
          disabled={loading}
          className="w-full bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-black font-semibold py-3 rounded-lg text-sm transition-colors"
        >
          {loading ? "Submitting..." : "Request Payout"}
        </button>
      </div>
    </>
  );
}
