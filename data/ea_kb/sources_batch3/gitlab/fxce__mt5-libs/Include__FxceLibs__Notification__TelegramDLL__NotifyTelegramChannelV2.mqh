//+------------------------------------------------------------------+
//|                              NotifyTelegramChannelFormatText.mqh |
//|                                 Copyright 2021, FXCE Company Ltd |
//|                                             https://www.fxce.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2021, FXCE Company Ltd"
#property link "https://www.fxce.com"

#include <FxceLibs/Notification/Telegram/CustomBot.mqh>
#include <FxceLibs/Common/HistoryPosition/HistoryPositionInfo.mqh>

CFxceHistoryPositionInfo hisPosInfo;

class CNotifyTelegramChannelFormatText
{
protected:
  string m_TeamName;
  string m_Status;
  ENUM_TIMEFRAMES m_Timefarmes;
  ENUM_POSITION_TYPE m_Type;
  double m_EntryPrice;
  double m_Stoploss;
  double m_Takeprofit;
  datetime m_EntryTime;
  string m_LinkAccount;
  double m_profitHis;
  double m_pip;
  double m_lot;

public:
  void SetTeamName(const string teamName)
  {
    m_TeamName = teamName;
  }

  void SetStatus(const string status)
  {
    m_Status = status;
  }
  void SetType(const int type)
  {
    m_Type = type;
  }
  void SetEntryPrice(const double entryPrice)
  {
    m_EntryPrice = entryPrice;
  }
  void SetStoploss(const double stopLoss)
  {
    m_Stoploss = stopLoss;
  }
  void SetTakeprofit(const double takeProfit)
  {
    m_Takeprofit = takeProfit;
  }
  void SetLinkAccount(const string linkAccount)
  {
    m_LinkAccount = linkAccount;
  }
  void SetProfitHis(const double profitHis)
  {
    m_profitHis = profitHis;
  }
  void SetPip(const double pip)
  {
    m_pip = pip;
  }
  void SetLot(const double lot)
  {
    m_lot = lot;
  }

  string FormatTextOpen()
  {
    string teamname = "「 ┅ ┅ ┅ " + m_TeamName + " ┅ ┅ ┅ 」";
    string eaName = "┌👤EA Name: \t" + StringSubstr(MQLInfoString(MQL_PROGRAM_NAME), 0, -4); //m_EA_Name
    string status = "┊└Status: " + m_Status;
    string symbol = "├Symbol: " + Symbol();
    string timeframe = "┊├TimeFarmes: " + StringSubstr(EnumToString(Period()), 7);
    string type = "┊├Type: " + StringSubstr(EnumToString(m_Type), 14);
    string entryPrice = "┊├Price: " + DoubleToString(m_EntryPrice, Digits());
    string stopLoss = "┊├Stoploss: " + DoubleToString(m_Stoploss, Digits());
    string takeProfit = "┊├Takeprofit: " + DoubleToString(m_Takeprofit, Digits());
    string entryTime = "└📅Time: " + TimeToString(TimeCurrent(), 3);
    string linkAccount = m_LinkAccount == "" || m_LinkAccount == NULL ? "" : "☞Follow me at: " + m_LinkAccount;

    return StringFormat("%s \n\n%s \n%s \n%s  \n%s  \n%s  \n%s  \n%s  \n%s \n%s \n\n%s", teamname, eaName, status, symbol, timeframe, type, entryPrice, stopLoss, takeProfit, entryTime,linkAccount);
  }

  string FormatTextClose()
  {
    string teamname = "「 ┅ ┅ ┅ " + m_TeamName + " ┅ ┅ ┅ 」";
    string eaName = "┌👤EA Name: \t" + StringSubstr(MQLInfoString(MQL_PROGRAM_NAME), 0, -4);
    string status = "┊└Status: " + m_Status;
    string symbol = "├Symbol: " + Symbol();
    string profitHis = "┊├Profit/loss: " + DoubleToString(m_profitHis, 2);
    string pips = "┊├Pips: " + DoubleToString(m_pip / Point() / 10, 1) + " pip";
    string lots = "┊├Lots: " + DoubleToString(m_lot, 2);
    string closeTime = "└📅Time: " + TimeToString(TimeCurrent(), 3);
    return StringFormat("%s \n\n%s \n%s \n%s  \n%s \n%s \n%s \n%s ", teamname, eaName, status, symbol, profitHis, pips, lots, closeTime);
  }

  bool SendToChannel(const string InpChatId, long chart_id, string imagname, int width = 1600, int height = 800, ENUM_ALIGN_MODE align_mode = ENUM_ALIGN_MODE::ALIGN_RIGHT, const string caption = NULL)
  {
    //FxceTelegram::CCustomBot bot;
    bool screenChart = ChartScreenShot(chart_id, imagname, 800, 800, align_mode);
    if (!screenChart)
    {
      Print("NOT!", screenChart);
      Print(FxceTelegram::GetErrorDescription(screenChart));
      return false;
    }
    return true;
  }
};