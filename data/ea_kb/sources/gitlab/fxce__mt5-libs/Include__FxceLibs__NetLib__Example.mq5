//+------------------------------------------------------------------+
//|                                                       TestWS.mq5 |
//|                                  Copyright 2021, MetaQuotes Ltd. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2021, MetaQuotes Ltd."
#property link      "https://www.mql5.com"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0
#include "netlib.mqh"
#include "JAson.mqh"

MqlNet mql_net;
CJAVal my_json;
string UrlForexFactory="https://nfs.faireconomy.media/ff_calendar_thisweek.json?version=cf3d12824aaaf7d270c38f50e4344be8";
//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int OnInit()
  {
//--- indicator buffers mapping
	//OpenUrlGetData();
	GetRequest();
//---
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
//| Custom indicator iteration function                              |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
//---
   
//--- return value of prev_calculated for next call
   return(rates_total);
  }

void OpenUrlGetData()
{
	string my_result;
	if(mql_net.Open("nfs.faireconomy.media",443))
	{
		bool my_request=mql_net.OpenURL(UrlForexFactory,my_result,false,"");
		if(my_request)
		{
			Print(my_result);		
			mql_net.Close();	
		}	
	}
	else
		Print("Can't access webservice");
}

void GetRequest()
{
	string my_result;
	if(mql_net.Open("nfs.faireconomy.media",443))
	{
		string headers = "Content-Type: application/json\r\nAccept: application/json\r\n";
		bool my_request=mql_net.Request(headers,"GET","/ff_calendar_thisweek.json?version=cf3d12824aaaf7d270c38f50e4344be8",my_result,"",false,"");
		if(my_request)
		{
			Print(my_result);		
			mql_net.Close();	
		}	
	}
	else
		Print("Can't access webservice");
}

void PostRequest()
{
	string my_result;
	my_json["user"]["login"]="test";
	my_json["user"]["password"]="TestPass";
	string string_json;
	my_json.Serialize(string_json);
		
	if(mql_net.Open("apifxce.com",443))
	{	
		string headers = "Content-Type: application/json\r\nAccept: application/json\r\nX-API-VERSION: v1\r\nX-API-TENANT: hook\r\n";
		bool my_request=mql_net.Request(headers,"POST","/api/users/sign_in",my_result,string_json,false,"");
		Print(my_result);	
	}
}