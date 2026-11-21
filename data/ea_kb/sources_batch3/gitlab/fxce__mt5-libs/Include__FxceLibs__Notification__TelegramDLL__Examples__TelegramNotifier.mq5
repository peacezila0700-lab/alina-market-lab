//+------------------------------------------------------------------+
//|                                             TelegramNotifier.mq5 |
//|                        Copyright 2021, MetaQuotes Software Corp. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2021, MetaQuotes Software Corp."
#property link "https://www.mql5.com"
#property version "1.00"

#include "../CustomBot.mqh"

input string InpBotToken = "Token";
input string InpChatId = "@chatchannel";
FxceTelegram::CCustomBot bot;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    bot.Token(InpBotToken);
    int ret = bot.GetMe();
    if(ret)
    {
        Print(FxceTelegram::GetErrorDescription(ret));
        return INIT_FAILED;
    }

    Print("Hello. I am ", bot.Name());
    bot.SendMessage(InpChatId, "Hello");
    return INIT_SUCCEEDED;
}