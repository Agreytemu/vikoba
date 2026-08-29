import { Link, useNavigate } from "react-router-dom";
import { TransactionForm } from "@/components/transactions/transactionForm";

const TransactionsEdit = () => {
  const navigate = useNavigate();

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <Link
          className="text-sm text-green-700 underline dark:text-green-400"
          to="/transactions"
        >
          ← Transactions
        </Link>
        <h1 className="text-2xl font-medium">New Transaction</h1>
        <p className="text-sm text-slate-500">
          Record a deposit or withdrawal against a member account.
        </p>
      </div>
      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft dark:border-slate-800 dark:bg-slate-900">
        <TransactionForm onSuccess={() => navigate("/transactions")} />
      </div>
    </div>
  );
};

export default TransactionsEdit;