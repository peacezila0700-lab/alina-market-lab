//+------------------------------------------------------------------+
//|                                            TelegramReChannel.mq5 |
//|                        Copyright 2021, MetaQuotes Software Corp. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2021, MetaQuotes Software Corp."
#property link "https://www.mql5.com"
#property version "1.00"


#include "../CustomBot.mqh"

input string InpBotToken = "token";


class CReconMessage : public FxceTelegram::CCustomBot
{
public:
    void ProcessMessages()
    {
        for (int i = 0; i < _chats.Total(); i++)
        {
            FxceTelegram::CCustomChat *chat = _chats.GetNodeAtIndex(i);
            if (!chat.NewOne.Done)
            {
                chat.NewOne.Done = true;
                string text = chat.NewOne.MessageText;
                StringToUpper(text);

                if (StringFind(text, "/HELLO", 0) >= 0)
                {
                    SendMessage(chat.Id, "Hello !");
                }

                if (StringFind(text, "/STOP") >= 0)
                {
                    SendMessage(chat.Id, "Do you need stop");
                }

                if (StringFind(text, "/CHECK", 0) >= 0)
                {
                    SendMessage(chat.Id, "What do you need to check");
                }
            }
        }
    }
};

CReconMessage bot;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+

int OnInit()
{
    bot.Token(InpBotToken);
    int ret = bot.GetMe();
    if (ret)
    {
        Print(FxceTelegram::GetErrorDescription(ret));
        return INIT_FAILED;
    }

    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+

void OnTick()
{
    bot.GetUpdates();
    bot.ProcessMessages();
}