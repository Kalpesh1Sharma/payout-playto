import axios from "axios";

const BASE = (import.meta.env.VITE_API_BASE_URL || '') + '/api/v1';


export const getMerchants = () => axios.get(`${BASE}/merchants/`);
export const getMerchantLedger = (id) => axios.get(`${BASE}/merchants/${id}/ledger/`);
export const getPayouts = (id) => axios.get(`${BASE}/merchants/${id}/payouts/`);
export const createPayout = (merchantId, amount_paise, bank_account_id, idempotencyKey) =>
  axios.post(
    `${BASE}/merchants/${merchantId}/payouts/create/`,
    { amount_paise, bank_account_id },
    { headers: { "Idempotency-Key": idempotencyKey } }
  );
