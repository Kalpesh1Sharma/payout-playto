import BalanceCard from "./BalanceCard";
import PayoutForm from "./PayoutForm";
import PayoutHistory from "./PayoutHistory";
import TransactionTable from "./TransactionTable";

export default function Dashboard({
  ledger,
  payouts,
  selectedMerchant,
  payoutForm,
  setPayoutForm,
  loading,
  onSubmitPayout,
  formatDate,
  formatINR,
}) {
  const totalCredits = ledger.entries
    .filter((entry) => entry.entry_type === "CREDIT")
    .reduce((acc, entry) => acc + entry.amount_paise, 0);

  return (
    <>
      <div className="grid grid-cols-3 gap-4 mb-8">
        <BalanceCard
          title="Available Balance"
          value={formatINR(ledger.available_balance_paise)}
          valueClassName="text-emerald-400"
        />
        <BalanceCard
          title="Held (In Transit)"
          value={formatINR(ledger.held_balance_paise)}
          valueClassName="text-yellow-400"
        />
        <BalanceCard title="Total Credits" value={formatINR(totalCredits)} valueClassName="text-white" />
      </div>

      <div className="grid grid-cols-2 gap-8">
        <div>
          <PayoutForm
            selectedMerchant={selectedMerchant}
            payoutForm={payoutForm}
            setPayoutForm={setPayoutForm}
            loading={loading}
            onSubmit={onSubmitPayout}
          />
          <TransactionTable entries={ledger.entries} formatDate={formatDate} formatINR={formatINR} />
        </div>

        <PayoutHistory payouts={payouts} formatDate={formatDate} formatINR={formatINR} />
      </div>
    </>
  );
}
