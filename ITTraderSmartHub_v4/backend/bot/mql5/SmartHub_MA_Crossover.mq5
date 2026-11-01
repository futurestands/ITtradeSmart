//+------------------------------------------------------------------+
//|                                     SmartHub_MA_Crossover.mq5    |
//|                    ITTrader SmartHub v5 Native Strategy Tester    |
//|        Reconciles MQL5 Strategy Tester with Python Backtesting   |
//+------------------------------------------------------------------+
#property copyright "ITTrader SmartHub v5"
#property link      "https://github.com/futurestands/ITtradeSmart"
#property version   "5.00"
#property indicator_applied_price PRICE_CLOSE

input int      InpFastMA_Period   = 10;     // Fast MA Period
input int      InpSlowMA_Period   = 30;     // Slow MA Period
input int      InpATR_Period      = 14;     // ATR Period
input double   InpATR_Multiplier  = 1.5;    // ATR Stop Loss Multiplier
input double   InpRewardRisk      = 2.0;    // Reward-to-Risk Ratio
input double   InpMaxRiskPct      = 0.5;    // Max Risk % Per Trade

int handle_fast_ma;
int handle_slow_ma;
int handle_atr;
datetime last_bar_time;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   handle_fast_ma = iMA(_Symbol, _Period, InpFastMA_Period, 0, MODE_SMA, PRICE_CLOSE);
   handle_slow_ma = iMA(_Symbol, _Period, InpSlowMA_Period, 0, MODE_SMA, PRICE_CLOSE);
   handle_atr     = iATR(_Symbol, _Period, InpATR_Period);

   if(handle_fast_ma == INVALID_HANDLE || handle_slow_ma == INVALID_HANDLE || handle_atr == INVALID_HANDLE)
     {
      Print("Error creating indicator handles");
      return(INIT_FAILED);
     }
   last_bar_time = 0;
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   IndicatorRelease(handle_fast_ma);
   IndicatorRelease(handle_slow_ma);
   IndicatorRelease(handle_atr);
  }

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
   // Closed-bar execution check
   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   double fast_ma[];
   double slow_ma[];
   double atr[];

   ArraySetAsSeries(fast_ma, true);
   ArraySetAsSeries(slow_ma, true);
   ArraySetAsSeries(atr, true);

   if(CopyBuffer(handle_fast_ma, 0, 1, 2, fast_ma) < 2) return;
   if(CopyBuffer(handle_slow_ma, 0, 1, 2, slow_ma) < 2) return;
   if(CopyBuffer(handle_atr, 0, 1, 1, atr) < 1) return;

   double curr_fast = fast_ma[0];
   double prev_fast = fast_ma[1];
   double curr_slow = slow_ma[0];
   double prev_slow = slow_ma[1];
   double atr_val   = atr[0];

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // Bullish Crossover
   if(prev_fast <= prev_slow && curr_fast > curr_slow)
     {
      double sl = ask - (atr_val * InpATR_Multiplier);
      double tp = ask + ((atr_val * InpATR_Multiplier) * InpRewardRisk);
      PrintFormat("MQL5 BUY SIGNAL @ %.5f | SL: %.5f | TP: %.5f", ask, sl, tp);
     }

   // Bearish Crossover
   if(prev_fast >= prev_slow && curr_fast < curr_slow)
     {
      double sl = bid + (atr_val * InpATR_Multiplier);
      double tp = bid - ((atr_val * InpATR_Multiplier) * InpRewardRisk);
      PrintFormat("MQL5 SELL SIGNAL @ %.5f | SL: %.5f | TP: %.5f", bid, sl, tp);
     }
  }
