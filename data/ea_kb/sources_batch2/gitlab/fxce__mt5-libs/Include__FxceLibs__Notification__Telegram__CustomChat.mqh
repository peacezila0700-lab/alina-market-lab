#include "CustomMessage.mqh"
namespace FxceTelegram
{
    class CCustomChat : public CObject
    {
    public:
        long Id;
        CCustomMessage Last;
        CCustomMessage NewOne;
        int State;
        datetime Time;

        CCustomChat()
        {
            Id = 0;
            State = 0;
            Time = 0;
        }
    };
}