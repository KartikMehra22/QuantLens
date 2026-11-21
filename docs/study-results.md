# Real-market rolling study

The local run on 21 November 2026 used Yahoo histories for six NSE equities and Nifty. The common price sample is 26 October 2023–20 November 2026. All three portfolios use 504 prior returns to predict each of 252 target dates, 13 November 2025–20 November 2026. Each target uses only preceding observations. Current value weights and symbols are selected retrospectively; this is not an investable strategy backtest.

| Portfolio | Model | MAE daily variance | RMSE daily variance | QLIKE |
| --- | --- | ---: | ---: | ---: |
| Diversified six | Historical (60d) | 9.6893136e-05 | 0.00015144799 | -8.206221 |
| Diversified six | EWMA | 9.7090907e-05 | 0.00014969679 | -8.244828 |
| Diversified six | GARCH(1,1) | 9.7486477e-05 | 0.000152027 | -8.204054 |
| Technology pair | Historical (60d) | 0.00037491725 | 0.00068578635 | -6.946355 |
| Technology pair | EWMA | 0.00038705257 | 0.00068798527 | -6.944854 |
| Technology pair | GARCH(1,1) | 0.00035608889 | 0.00069059256 | -6.918369 |
| Banking pair | Historical (60d) | 0.00016120834 | 0.00031775218 | -7.747280 |
| Banking pair | EWMA | 0.00015607262 | 0.00030641015 | -7.917363 |
| Banking pair | GARCH(1,1) | 0.00015573747 | 0.00030756397 | -7.874495 |

EWMA has the lowest QLIKE and RMSE in diversified and banking samples. The historical baseline has the lowest QLIKE and RMSE in technology. MAE ranks the models differently. No significance test or general superiority claim is made. QLIKE is mean(log(h) + r²/h), can be negative, and must be compared on the same variance scale and dates. Squared daily returns are a noisy proxy for variance.

Reproduce with `uv run python ../experiments/research_study.py` from `backend/`. Saved private JSON inputs and cached downloads are under ignored `experiments/results/`. The runner creates a separate study account, caches data and records holdings, exact dates, return inputs, forecasts and assumptions. For the same input series, `experiments/evaluate.py` and the pure `evaluate` routine reproduce model losses. Later provider revisions or refreshed data may change results. The UI evaluates each portfolio on its own available dates, so its sample can differ from this fixed intersection.

Full raw downloaded datasets are not included in the public source. Price conventions: [yfinance documentation](https://ranaroussi.github.io/yfinance/advanced/price_adjustment.html). Model reference: [arch forecasting](https://arch.readthedocs.io/en/stable/univariate/univariate_volatility_forecasting.html).
