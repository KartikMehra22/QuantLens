export type User = { id: string; name: string; email: string };
export type AuthResponse = {
  access_token: string;
  user: User;
  expires_in: number;
};
export type Portfolio = {
  id: string;
  name: string;
  data_mode: "synthetic" | "yahoo" | "csv";
};
export type Instrument = {
  id: string;
  symbol: string;
  name: string;
  exchange: string;
  sector: string;
  color: string;
};
export type Holding = Omit<Instrument, "id"> & {
  id: string;
  instrument_id: string;
  quantity: number;
  average_cost: number;
  price: number;
  value: number;
  invested: number;
  pnl: number;
  pnl_pct: number;
  weight: number;
  risk_contribution?: number;
};
export type Metrics = {
  observations: number;
  annualized_volatility: number;
  sharpe_ratio: number | null;
  max_drawdown: number;
  var_95: number;
  cvar_95: number;
  cumulative_return: number;
  cagr: number;
  risk_free_rate: number;
};
export type Summary = {
  portfolio_id: string;
  name: string;
  data_mode: Portfolio["data_mode"];
  as_of: string | null;
  holdings: Holding[];
  invested: number;
  value: number;
  pnl: number;
  pnl_pct: number;
  series: { date: string; value: number }[];
  metrics: Metrics | null;
  diversification: {
    symbols: string[];
    correlations: (number | null)[][];
    concentration_hhi: number;
  } | null;
  warnings: string[];
  methodology: string;
  period_start?: string;
  period_end?: string;
};
export type Forecast = {
  as_of: string;
  horizon: number;
  observations: number;
  models: Record<string, number[]>;
  parameters: Record<string, number>;
  warning: string;
};
export type Scenario = {
  before: number;
  after: number;
  change: number;
  change_pct: number;
  holdings: (Holding & { change: number; shock: number })[];
};
export type Report = {
  id: string;
  kind: string;
  created_at: string;
  as_of: string;
  data_mode: string;
};
