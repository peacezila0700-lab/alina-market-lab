#include <Object.mqh>
namespace FxceTelegram
{
    class CCustomMessage : public CObject
    {
    public:
        bool Done;
        long UpdateId;
        long MessageId;
        //---
        long FromId;
        string FromFirstName;
        string FromLastName;
        string FromUserName;
        //---
        long ChatId;
        string ChatFirstName;
        string ChatLastName;
        string ChatUserName;
        string ChatType;
        //---
        datetime MessageDate;
        string MessageText;

        CCustomMessage()
        {
            Done = false;
            UpdateId = 0;
            MessageId = 0;
            FromId = 0;
            FromFirstName = NULL;
            FromLastName = NULL;
            FromUserName = NULL;
            ChatId = 0;
            ChatFirstName = NULL;
            ChatLastName = NULL;
            ChatUserName = NULL;
            ChatType = NULL;
            MessageDate = 0;
            MessageText = NULL;
        }
    };
}