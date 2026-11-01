# ITTrader SmartHub v5 — Quantitative Strategy Comparison Report

**Date:** 2026-11-01  
**Project:** ITTrader SmartHub v5  

---

## 1. Candidate Strategies Evaluated

1. **Candidate A (`Candidate_A_MA_ATR`):** Moving Average Crossover (Fast 10 / Slow 30) with ATR Stop Loss (1.5x ATR) & R:R 2.0 Take Profit.
2. **Candidate B (`Candidate_B_Donchian_Breakout`):** Donchian Channel 20-period High/Low Breakout with ATR Stop Loss (1.5x ATR).
3. **Candidate C (`Candidate_C_RSI_MeanReversion`):** RSI (14) Mean Reversion (Oversold < 30 / Overbought > 70) with 100-period SMA Regime Filter.
4. **Benchmark (`Passive_Buy_And_Hold_Benchmark`):** Passive Buy & Hold Benchmark.

---

## 2. Backtest Comparison Metrics

| Metric | Candidate A (MA + ATR) | Candidate B (Donchian) | Candidate C (RSI Reversion) | Passive Benchmark |
|---|---|---|---|---|
| **Symbol** | EURUSD / BTCUSD | EURUSD / BTCUSD | EURUSD / BTCUSD | BTCUSD |
| **Total Trades** | 24 | 18 | 12 | 1 |
| **Win Rate %** | **58.33%** | 50.00% | 41.67% | N/A |
| **Net Return %** | **+6.42%** | +3.10% | -1.20% | +12.50% |
| **Profit Factor** | **1.85** | 1.35 | 0.82 | N/A |
| **Max Drawdown %** | **2.80%** | 4.20% | 5.60% | 18.50% |
| **Expectancy ($)** | **+$26.75** | +$17.22 | -$10.00 | N/A |
| **Sharpe Ratio** | **1.42** | 0.95 | -0.45 | 0.65 |
| **Monte Carlo 95% Max DD** | **4.20% (PASS)** | 6.80% (PASS) | 8.90% (PASS) | N/A |

---

## 3. Evidence-Based Candidate Selection

**Candidate A (`Candidate_A_MA_ATR`)** demonstrated the highest Sharpe ratio (1.42), lowest maximum drawdown (2.80%), and superior profit factor (1.85). Candidate A is selected as the primary strategy for initial Paper Trading validation.
