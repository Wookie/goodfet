#include <cc1110.h>
#include "cc1110-ext.h"

char __xdata at 0xfe00 packet[256] ;
void carrier(){
  // Set the system clock source to HS XOSC and max CPU speed,
  // ref. [clk]=>[clk_xosc.c]
  SLEEP &= ~SLEEP_OSC_PD;
  while( !(SLEEP & SLEEP_XOSC_S) );
  CLKCON = (CLKCON & ~(CLKCON_CLKSPD | CLKCON_OSC)) | CLKSPD_DIV_1;
  while (CLKCON & CLKCON_OSC);
  SLEEP |= SLEEP_OSC_PD;


  /* Setup radio with settings from SmartRF® Studio. The default settings are
   * used, except that "unmodulated" is chosen in the "Simple RX tab". This
   * results in an umodulated carrier with a frequency of approx. 2.433 GHz.
   */
  //FSCTRL1   = 0x0A;   // Frequency synthesizer control.
  //FSCTRL0   = 0x00;   // Frequency synthesizer control.
  
  
  
  MDMCFG4   = 0x86;   // Modem configuration.
  MDMCFG3   = 0x83;   // Modem configuration.
  MDMCFG2   = 0x30;   // Modem configuration.
  MDMCFG1   = 0x22;   // Modem configuration.
  MDMCFG0   = 0xF8;   // Modem configuration.
  
  /*
  CHANNR    = 0x00;   // Channel number.
  DEVIATN   = 0x00;   // Modem deviation setting (when FSK modulation is enabled).
  FREND1    = 0x56;   // Front end RX configuration.
  FREND0    = 0x10;   // Front end RX configuration.
  MCSM0     = 0x14;   // Main Radio Control State Machine configuration.
  FOCCFG    = 0x16;   // Frequency Offset Compensation Configuration.
  BSCFG     = 0x6C;   // Bit synchronization Configuration.
  AGCCTRL2  = 0x03;   // AGC control.
  AGCCTRL1  = 0x40;   // AGC control.
  AGCCTRL0  = 0x91;   // AGC control.
  FSCAL3    = 0xE9;   // Frequency synthesizer calibration.
  FSCAL2    = 0x2a;   // Frequency synthesizer calibration.
  FSCAL1    = 0x00;   // Frequency synthesizer calibration.
  FSCAL0    = 0x1f;   // Frequency synthesizer calibration
  
  TEST2     = 0x88;   // Various test settings.
  TEST1     = 0x31;   // Various test settings.
  TEST0     = 0x09;   // Various test settings.
  
  //FE is too high
  PA_TABLE0 = 0xFF;   // PA output power setting.
  PKTCTRL1  = 0x04;   // Packet automation control.
  PKTCTRL0  = 0x22;   // Packet automation control.
  ADDR      = 0x00;   // Device address.
  PKTLEN    = 0xFF;   // Packet length.
  */
  /* Settings not from SmartRF® Studio. Setting both sync word registers to
   * 0xAA = 0b10101010, i.e., the same as the preamble pattern. Not necessary,
   * but gives control of what the radio attempts to transmit.
   */
  
  //These sync values are better for jamming, but they break reception.
  //SYNC1     = 0xAA;
  //SYNC0     = 0xAA;

  /* Put radio in TX. 
  RFST      = RFST_STX;
  while ((MARCSTATE & MARCSTATE_MARC_STATE) != MARC_STATE_TX);
  */

  
#define RFON RFST = RFST_SIDLE; RFST = RFST_STX; while ((MARCSTATE & MARCSTATE_MARC_STATE) != MARC_STATE_TX);
#define RFOFF RFST = RFST_SIDLE; //while ((MARCSTATE & MARCSTATE_MARC_STATE) != MARC_STATE_IDLE);
  //RFON;
  //while(1);  
  
  
}


void sleepMillis(int ms) {
	int j;
	while (--ms > 0) { 
		for (j=0; j<1200;j++); // about 1 millisecond
	};
}


//! Reflexively jam on the present channel by responding to a signal with a carrier wave.
void main(){
  unsigned char threshold=packet[0], i=0, rssi=0;;
  
  //Disable interrupts.
  RFTXRXIE=0;
  
  //carrier();
  
  //idle a bit.
  RFST=RFST_SIDLE;
  while(MARCSTATE!=MARC_STATE_IDLE);

  while(1){
    //idle a bit.
    RFST=RFST_SFSTXON;
    while(MARCSTATE!=MARC_STATE_FSTXON);
    
    
    sleepMillis(5);
    rxwait();
    
    //idle w/ oscillator
    RFST=RFST_SFSTXON;
    while(MARCSTATE!=MARC_STATE_FSTXON);
    //HALT;
    
    //RFOFF;
    
    //SYNC1=0xAA;
    //SYNC0=0xAA;
    
    //Transmit carrier for 10ms
    carrier();
    RFON;
    HALT;
  }
}

//! Receives a packet out of the radio from 0xFE00.
void rxwait(){
  unsigned char len=16, i=0;
  
  do{
    //1-out the buffer.
    for(i=0;i<64;i++)
      packet[i]=0xFF;
    i=0;
    
    //Disable interrupts.
    RFTXRXIE=0;
    
    //idle a bit.
    RFST=RFST_SIDLE;
    while(MARCSTATE!=MARC_STATE_IDLE);
    
    //Begin to receive.
    RFST=RFST_SRX;
    while(MARCSTATE!=MARC_STATE_RX);
    
    if(PKTCTRL0&1){
      //auto length
      while(i<len+3){ //len+3 if status is appended.
	while(!RFTXRXIF); //Wait for byte to be ready.
	RFTXRXIF=0;      //Clear the flag.
	
	packet[i++]=RFD; //Grab the next byte.
	len=packet[0];   //First byte of the packet is the length.
      }
    }else{
      //Fixed length
      packet[i++]=PKTLEN;
      while(i<PKTLEN){
	while(!RFTXRXIF); //Wait for byte to be ready.
	RFTXRXIF=0;      //Clear the flag.
	
	packet[i++]=RFD; //Grab the next byte.
      }
    }
    RFST = RFST_SIDLE; //End receive.
    
    //This while loop can be used for filtering.  Unused for now.
  }while(0); //packet[0]==(char) 0x0f || packet[1]==(char) 0xFF || packet[9]==(char) 0x03);
}

