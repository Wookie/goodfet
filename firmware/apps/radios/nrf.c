/*! \file nrf.c
  \author Travis Goodspeed
  \brief NordicRF Register Interface
*/

//Higher level left to client application.

#include "platform.h"
#include "command.h"

#include <signal.h>
#include <io.h>
#include <iomacros.h>

#include "nrf.h"
#include "spi.h"


#define RADIOACTIVE SETCE
#define RADIOPASSIVE CLRCE

//! Set up the pins for NRF mode.
void nrfsetup(){
  SETSS;
  P5DIR&=~MISO;
  P5DIR|=MOSI+SCK;
  DIRSS;
  DIRCE;
  
  //Begin a new transaction.
  CLRSS; 
  SETSS;
}

//! Read and write an NRF byte.
u8 nrftrans8(u8 byte){
  register unsigned int bit;
  //This function came from the NRF Wikipedia article.
  //Minor alterations.
  
  for (bit = 0; bit < 8; bit++) {
    /* write MOSI on trailing edge of previous clock */
    if (byte & 0x80)
      SETMOSI;
    else
      CLRMOSI;
    byte <<= 1;
 
    SETCLK;
  
    /* read MISO on trailing edge */
    byte |= READMISO;
    CLRCLK;
  }
  
  return byte;
}


//! Writes a register
u8 nrf_regwrite(u8 reg, const u8 *buf, int len){
  CLRSS;
  
  reg=nrftrans8(reg);
  while(len--)
    nrftrans8(*buf++);
  
  SETSS;
  return reg;//status
}
//! Reads a register
u8 nrf_regread(u8 reg, u8 *buf, int len){
  CLRSS;
  
  reg=nrftrans8(reg);
  while(len--)
    *buf++=nrftrans8(0);
  
  SETSS;
  return reg;//status
}

//! Handles a Nordic RF command.
void nrfhandle(unsigned char app,
	       unsigned char verb,
	       unsigned long len){
  unsigned long i;
  
  //Drop CE to passify radio.
  RADIOPASSIVE;
  //Raise !SS to end transaction, just in case we forgot.
  SETSS;
  nrfsetup();
  
  switch(verb){
    //PEEK and POKE might come later.
  case READ:  
  case WRITE:
    CLRSS; //Drop !SS to begin transaction.
    for(i=0;i<len;i++)
      cmddata[i]=nrftrans8(cmddata[i]);
    SETSS;  //Raise !SS to end transaction.
    txdata(app,verb,len);
    break;

  case PEEK://Grab NRF Register
    CLRSS; //Drop !SS to begin transaction.
    nrftrans8(NRF_R_REGISTER | cmddata[0]); //000A AAAA
    for(i=1;i<len;i++)
      cmddata[i]=nrftrans8(cmddata[i]);
    SETSS;  //Raise !SS to end transaction.
    txdata(app,verb,len);
    break;
    
  case POKE://Poke NRF Register
    CLRSS; //Drop !SS to begin transaction.
    nrftrans8(NRF_W_REGISTER | cmddata[0]); //001A AAAA
    for(i=1;i<len;i++)
      cmddata[i]=nrftrans8(cmddata[i]);
    SETSS;  //Raise !SS to end transaction.
    txdata(app,verb,len);
    break;
  case SETUP:
    nrfsetup();
    txdata(app,verb,0);
    break;
  case NRF_RX:
    RADIOPASSIVE;
    //Get the packet.
    CLRSS;
    nrftrans8(NRF_R_RX_PAYLOAD);
    for(i=0;i<32;i++)
      cmddata[i]=nrftrans8(0xde);
    SETSS;
    //no break
    txdata(app,verb,32);
    break;
  case NRF_RX_FLUSH:
    //Flush the buffer.
    CLRSS;
    nrftrans8(NRF_FLUSH_RX);
    SETSS;
    
    //Return the packet.
    txdata(app,verb,32);
    break;
  case NRF_TX:
  case NRF_TX_FLUSH:
  default:
    debugstr("Not yet supported.");
    txdata(app,verb,0);
    break;
  }
  

  SETSS;//End session
  RADIOACTIVE;
}
