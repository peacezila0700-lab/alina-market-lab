//+------------------------------------------------------------------+
//| Daily Loss and Profit Lock                       XPro by Xander  |
//| Version 1.0  |  2026-11-20  |  MetaTrader 5                      |
//| Developer: Cristhian Gaibor (Xander)                             |
//| Profile:   https://www.mql5.com/en/users/09151993a               |
//+------------------------------------------------------------------+
// XPro by Xander. Tested code, compiles clean and runs on demo and
// live accounts as it is. Built from more than 10 years of trading
// and coding experience, so you can use it today or take it as the
// base for your own EA or indicator. You will find more tools like
// this one on my profile. If something is not clear, ask in the
// comments and I will answer. Results depend on your settings, your
// broker and your risk management, so test your configuration first.
// Provided as is, use at your own risk.
// Updates and new tools first on my MQL5 channel:
// https://www.mql5.com/en/channels/xander
//+------------------------------------------------------------------+
// CHANGELOG
// v1.0 - 2026-11-20 - Initial release
//+------------------------------------------------------------------+
#property copyright   "Copyright 2026, Cristhian Gaibor (Xander)"
#property link        "https://www.mql5.com/en/users/09151993a"
#property version     "1.00"
#property description "XPro by Xander. Tested code, compiles clean, ready for demo and live accounts."
#property description "Use it as it is or as the base for your own EA or indicator. 10+ years of experience behind it."
#property description "More tools on my profile. Updates first on my MQL5 channel: mql5.com/en/channels/xander"

#include <Trade\Trade.mqh>

//--- enums
enum ENUM_XP_LIMIT_MODE
  {
   XP_LIMIT_PERCENT = 0, // Percent of the equity at the day start
   XP_LIMIT_MONEY   = 1  // Money in account currency
  };

enum ENUM_XP_SCOPE
  {
   XP_SCOPE_ACCOUNT = 0, // Every position on the account
   XP_SCOPE_MAGIC   = 1  // Only positions with the magic number below
  };

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input string sep0              = "★ Daily Loss and Profit Lock";     // ══ XPro by Xander ══
input string sep1              = "══════ DAILY LIMITS ══════";       // ─────────────────────
input ENUM_XP_LIMIT_MODE InpLimitMode = XP_LIMIT_PERCENT;           // How the limits are measured
input double InpDailyLoss      = 4.0;    // Daily loss limit (percent or money, 0 = off)
input double InpDailyProfit    = 0.0;    // Daily profit target that also locks the day (0 = off)
input double InpMaxLossTotal   = 0.0;    // Overall loss from the starting balance below (0 = off)
input double InpStartBalance   = 0.0;    // Starting balance for the overall limit (0 = balance when attached)

input string sep2              = "══════ CLOSE / EXIT ══════";       // ─────────────────────
input ENUM_XP_SCOPE InpScope   = XP_SCOPE_ACCOUNT;                  // Positions the guard controls
input long   InpMagicFilter    = 0;      // Magic number (only for the magic scope)
input bool   InpDeletePending  = true;   // Delete pending orders when a limit is hit
input bool   InpBlockNewTrades = true;   // Close any new position until the next day

input string sep3              = "══════ RISK PROTECTION ══════";    // ─────────────────────
input string InpDayStart       = "00:00"; // Day start (HH:MM, server time)
input int    InpWarnPercent    = 75;     // Warning when this percent of the daily limit is used (0 = off)

input string sep4              = "══════ EXPERT SETTINGS ══════";    // ─────────────────────
input int    InpSlippage       = 50;     // Max slippage when closing (points)
input bool   InpAlertPopup     = true;   // Popup alert when a limit is hit
input bool   InpAlertPush      = false;  // Push notification to the phone
input bool   InpShowInfo       = true;   // Show status on chart

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
#define XP_NAME "Daily Loss and Profit Lock"
#define XP_DAY  86400

CTrade   XP_trade;
int      XP_dayStartMin = 0;     // day start, minutes from midnight
datetime XP_dayKey      = 0;     // start time of the current trading day
double   XP_dayEquity   = 0.0;   // equity at the day start
double   XP_startBal    = 0.0;   // reference for the overall limit
bool     XP_locked      = false; // daily lock active
bool     XP_lockedTotal = false; // overall limit hit, stays until the EA is removed
string   XP_reason      = "";
bool     XP_warned      = false;

//+------------------------------------------------------------------+
//| Reads HH:MM into minutes from midnight                           |
//+------------------------------------------------------------------+
bool XP_ParseTime(const string text,int &minutes)
  {
   string parts[];
   if(StringSplit(text,StringGetCharacter(":",0),parts)!=2) return(false);
   int h=(int)StringToInteger(parts[0]);
   int m=(int)StringToInteger(parts[1]);
   if(h<0 || h>23 || m<0 || m>59) return(false);
   minutes=h*60+m;
   return(true);
  }

//+------------------------------------------------------------------+
//| Init                                                             |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(!XP_ParseTime(InpDayStart,XP_dayStartMin))
     {
      Print("[", XP_NAME, "] The day start must be written as HH:MM.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpDailyLoss<0.0 || InpDailyProfit<0.0 || InpMaxLossTotal<0.0 || InpStartBalance<0.0 ||
      InpWarnPercent<0 || InpWarnPercent>=100)
     {
      Print("[", XP_NAME, "] Limits cannot be negative and the warning must be below 100 percent.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpLimitMode==XP_LIMIT_PERCENT && (InpDailyLoss>=100.0 || InpMaxLossTotal>=100.0))
     {
      Print("[", XP_NAME, "] In percent mode the loss limits must be below 100.");
      return(INIT_PARAMETERS_INCORRECT);
     }

   XP_trade.SetDeviationInPoints((ulong)InpSlippage);
   XP_trade.SetAsyncMode(false);

   XP_startBal=(InpStartBalance>0.0 ? InpStartBalance : AccountInfoDouble(ACCOUNT_BALANCE));
   XP_dayKey=0;
   XP_CheckNewDay();
   EventSetTimer(1);
   Print("[", XP_NAME, "] Started. Day start equity ", DoubleToString(XP_dayEquity,2), " ",
         AccountInfoString(ACCOUNT_CURRENCY), ", daily loss limit ", XP_LimitText(InpDailyLoss));
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Deinit                                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   Comment("");
  }

//+------------------------------------------------------------------+
//| The guard runs on every tick and every second, so it also works  |
//| when the chart symbol is quiet                                   |
//+------------------------------------------------------------------+
void OnTick()  { XP_Guard(); }
void OnTimer() { XP_Guard(); }

//+------------------------------------------------------------------+
//| Main check                                                       |
//+------------------------------------------------------------------+
void XP_Guard()
  {
   XP_CheckNewDay();
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   double dayResult=equity-XP_dayEquity;

   if(!XP_locked && !XP_lockedTotal)
     {
      double lossLimit=XP_Amount(InpDailyLoss);
      double profitLimit=XP_Amount(InpDailyProfit);

      if(InpDailyLoss>0.0 && -dayResult>=lossLimit)
         XP_Lock("daily loss limit",false);
      else
         if(InpDailyProfit>0.0 && dayResult>=profitLimit)
            XP_Lock("daily profit target",false);

      if(InpMaxLossTotal>0.0)
        {
         double totalLimit=(InpLimitMode==XP_LIMIT_PERCENT ? XP_startBal*InpMaxLossTotal/100.0 : InpMaxLossTotal);
         if(XP_startBal-equity>=totalLimit)
            XP_Lock("overall loss limit",true);
        }

      //--- early warning, once per day
      if(!XP_locked && !XP_lockedTotal && !XP_warned && InpDailyLoss>0.0 && InpWarnPercent>0 &&
         -dayResult>=lossLimit*InpWarnPercent/100.0)
        {
         XP_warned=true;
         XP_Notify(StringFormat("%d%% of the daily loss limit used (%s)",InpWarnPercent,DoubleToString(dayResult,2)));
        }
     }

   //--- while locked, nothing new stays open
   if((XP_locked || XP_lockedTotal) && InpBlockNewTrades)
     {
      if(XP_CountControlled()>0) XP_CloseAll();
      if(InpDeletePending) XP_DeletePending();
     }

   if(InpShowInfo) XP_ShowInfo(equity,dayResult);
  }

//+------------------------------------------------------------------+
//| New trading day: new reference equity, daily lock released       |
//+------------------------------------------------------------------+
void XP_CheckNewDay()
  {
   datetime now=TimeCurrent();
   if(now==0) now=TimeLocal();
   datetime key=now-(now%XP_DAY)+XP_dayStartMin*60;
   if(key>now) key-=XP_DAY;
   if(key==XP_dayKey) return;
   XP_dayKey=key;
   XP_dayEquity=AccountInfoDouble(ACCOUNT_EQUITY);
   XP_warned=false;
   if(XP_locked)
      Print("[", XP_NAME, "] New day. Trading is allowed again.");
   XP_locked=false;
   XP_reason=(XP_lockedTotal ? XP_reason : "");
  }

//+------------------------------------------------------------------+
//| Locks the day (or the account) and closes what it controls       |
//+------------------------------------------------------------------+
void XP_Lock(const string why,const bool total)
  {
   if(total) XP_lockedTotal=true;
   else      XP_locked=true;
   XP_reason=why;
   XP_CloseAll();
   if(InpDeletePending) XP_DeletePending();
   XP_Notify(StringFormat("%s hit. Equity %s, day start %s. Positions closed%s.",why,
             DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY),2),DoubleToString(XP_dayEquity,2),
             (total ? ", trading blocked until the EA is removed" : ", trading blocked until the next day")));
  }

//+------------------------------------------------------------------+
//| Close and delete only what the scope allows                      |
//+------------------------------------------------------------------+
bool XP_Controlled(const long magic)
  {
   return(InpScope==XP_SCOPE_ACCOUNT || magic==InpMagicFilter);
  }

int XP_CountControlled()
  {
   int count=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(XP_Controlled(PositionGetInteger(POSITION_MAGIC))) count++;
     }
   return(count);
  }

void XP_CloseAll()
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(!XP_Controlled(PositionGetInteger(POSITION_MAGIC))) continue;
      string sym=PositionGetString(POSITION_SYMBOL);
      if(XP_trade.PositionClose(ticket,(ulong)InpSlippage))
         Print("[", XP_NAME, "] closed #", ticket, " ", sym);
      else
         Print("[", XP_NAME, "] could not close #", ticket, " ", sym, ". Retcode ", XP_trade.ResultRetcode());
     }
  }

void XP_DeletePending()
  {
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      ulong ticket=OrderGetTicket(i);
      if(ticket==0 || !OrderSelect(ticket)) continue;
      if(!XP_Controlled(OrderGetInteger(ORDER_MAGIC))) continue;
      if(XP_trade.OrderDelete(ticket))
         Print("[", XP_NAME, "] deleted pending order #", ticket);
     }
  }

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
double XP_Amount(const double value)
  {
   return(InpLimitMode==XP_LIMIT_PERCENT ? XP_dayEquity*value/100.0 : value);
  }

string XP_LimitText(const double value)
  {
   if(value<=0.0) return("off");
   if(InpLimitMode==XP_LIMIT_PERCENT)
      return(DoubleToString(value,2)+"% ("+DoubleToString(XP_Amount(value),2)+" "+AccountInfoString(ACCOUNT_CURRENCY)+")");
   return(DoubleToString(value,2)+" "+AccountInfoString(ACCOUNT_CURRENCY));
  }

void XP_Notify(const string text)
  {
   string msg="["+XP_NAME+"] "+text;
   Print(msg);
   if(MQLInfoInteger(MQL_TESTER)) return;
   if(InpAlertPopup) Alert(msg);
   if(InpAlertPush)  SendNotification(msg);
  }

//+------------------------------------------------------------------+
//| Plain text status on the chart                                   |
//+------------------------------------------------------------------+
void XP_ShowInfo(const double equity,const double dayResult)
  {
   string cur=AccountInfoString(ACCOUNT_CURRENCY);
   string state="ACTIVE, trading allowed";
   if(XP_locked)      state="LOCKED for today: "+XP_reason;
   if(XP_lockedTotal) state="LOCKED: "+XP_reason+" (remove the EA to reset)";
   string txt=XP_NAME+"  |  XPro by Xander\n";
   txt+="Status: "+state+"\n";
   txt+="Day start equity: "+DoubleToString(XP_dayEquity,2)+" "+cur+"   Equity now: "+DoubleToString(equity,2)+
        "   Day result: "+DoubleToString(dayResult,2)+"\n";
   txt+="Daily loss limit: "+XP_LimitText(InpDailyLoss)+"   Daily target: "+XP_LimitText(InpDailyProfit)+"\n";
   double totalAmt=(InpLimitMode==XP_LIMIT_PERCENT ? XP_startBal*InpMaxLossTotal/100.0 : InpMaxLossTotal);
   txt+="Overall limit: "+(InpMaxLossTotal>0.0 ? DoubleToString(totalAmt,2)+" "+cur+" below "+DoubleToString(XP_startBal,2) : "off")+
        "   Scope: "+(InpScope==XP_SCOPE_ACCOUNT ? "whole account" : "magic "+IntegerToString(InpMagicFilter))+
        "   Day starts "+InpDayStart+" server time";
   Comment(txt);
  }
//+------------------------------------------------------------------+
