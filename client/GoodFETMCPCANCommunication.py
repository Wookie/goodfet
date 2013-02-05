#!/usr/bin/env python
# GoodFET SPI Flash Client
#
# (C) 2012 Travis Goodspeed <travis at radiantmachines.com>
#
#
# Ted's working copy
#   1) getting hot reads on frequency
#   2) allow sniffing in "normal" mode to get ack bits
#       --check if that's whats causing error flags in board-to-board transmission
#
#

import sys;
import binascii;
import array;
import csv, time, argparse;
import datetime
import os
from random import randrange
from GoodFETMCPCAN import GoodFETMCPCAN;
from intelhex import IntelHex;
import Queue

class GoodFETMCPCANCommunication:
    
    def __init__(self):
       self.client=GoodFETMCPCAN();
       self.client.serInit()
       self.client.MCPsetup();
       self.DATALOCATION = "../../contrib/ThayerData/"
       

    
    def printInfo(self):
        
        self.client.MCPreqstatConfiguration();
        
        print "MCP2515 Info:\n\n";
        
        print "Mode: %s" % self.client.MCPcanstatstr();
        print "Read Status: %02x" % self.client.MCPreadstatus();
        print "Rx Status:   %02x" % self.client.MCPrxstatus();
        print "Error Flags:  %02x" % self.client.peek8(0x2D);
        print "Tx Errors:  %3d" % self.client.peek8(0x1c);
        print "Rx Errors:  %3d\n" % self.client.peek8(0x1d);
        
        print "Timing Info:";
        print "CNF1: %02x" %self.client.peek8(0x2a);
        print "CNF2: %02x" %self.client.peek8(0x29);
        print "CNF3: %02x\n" %self.client.peek8(0x28);
        print "RXB0 CTRL: %02x" %self.client.peek8(0x60);
        print "RXB1 CTRL: %02x" %self.client.peek8(0x70);
        
        print "RX Info:";
        print "RXB0: %02x" %self.client.peek8(0x60);
        print "RXB1: %02x" %self.client.peek8(0x70);
        print "RXB0 masks: %02x, %02x, %02x, %02x" %(self.client.peek8(0x20), self.client.peek8(0x21), self.client.peek8(0x22), self.client.peek8(0x23));
        print "RXB1 masks: %02x, %02x, %02x, %02x" %(self.client.peek8(0x24), self.client.peek8(0x25), self.client.peek8(0x26), self.client.peek8(0x27));

        
        print "RX Buffers:"
        packet0=self.client.readrxbuffer(0);
        packet1=self.client.readrxbuffer(1);
        for foo in [packet0, packet1]:
           print self.client.packet2str(foo);
           
    def reset(self):
        self.client.MCPsetup();
    
    
    ##########################
    #   SNIFF
    ##########################
         
    def sniff(self,freq,duration,description, verbose=True, comment=None, filename=None, standardid=None, debug=False, faster=False, parsed=True, data = None):
        
        #reset eveything on the chip
        self.client.serInit() 
        self.reset()
          
        #### ON-CHIP FILTERING
        if(standardid != None):
            if( comment == None):
                comment = ""
            self.client.MCPreqstatConfiguration();  
            self.client.poke8(0x60,0x26); # set RXB0 CTRL register to ONLY accept STANDARD messages with filter match (RXM1=0, RMX0=1, BUKT=1)
            self.client.poke8(0x20,0xFF); #set buffer 0 mask 1 (SID 10:3) to FF
            self.client.poke8(0x21,0xE0); #set buffer 0 mask 2 bits 7:5 (SID 2:0) to 1s
            if(len(standardid)>2):
               self.client.poke8(0x70,0x20); # set RXB1 CTRL register to ONLY accept STANDARD messages with filter match (RXM1=0, RMX0=1)
               self.client.poke8(0x24,0xFF); #set buffer 1 mask 1 (SID 10:3) to FF
               self.client.poke8(0x25,0xE0); #set buffer 1 mask 2 bits 7:5 (SID 2:0) to 1s 
            
            for filter,ID in enumerate(standardid):
        
               if (filter==0):
                RXFSIDH = 0x00;
                RXFSIDL = 0x01;
               elif (filter==1):
                RXFSIDH = 0x04;
                RXFSIDL = 0x05;
               elif (filter==2):
                RXFSIDH = 0x08;
                RXFSIDL = 0x09;
               elif (filter==3):
                RXFSIDH = 0x10;
                RXFSIDL = 0x11;
               elif (filter==4):
                RXFSIDH = 0x14;
                RXFSIDL = 0x15;
               else:
                RXFSIDH = 0x18;
                RXFSIDL = 0x19;
        
               #### split SID into different regs
               SIDlow = (ID & 0x07) << 5;  # get SID bits 2:0, rotate them to bits 7:5
               SIDhigh = (ID >> 3) & 0xFF; # get SID bits 10:3, rotate them to bits 7:0
               
               #write SID to regs 
               self.client.poke8(RXFSIDH,SIDhigh);
               self.client.poke8(RXFSIDL, SIDlow);
        
               if (verbose == True):
                   print "Filtering for SID %d (0x%02xh) with filter #%d"%(ID, ID, filter);
               comment += ("f%d" %(ID))
        
        
        self.client.MCPsetrate(freq);
        
        # This will handle the files so that we do not loose them. each day we will create a new csv file
        if( filename==None):
            #get folder information (based on today's date)
            now = datetime.datetime.now()
            datestr = now.strftime("%Y%m%d")
            path = self.DATALOCATION+datestr+".csv"
            filename = path
            
        
        outfile = open(filename,'a');
        dataWriter = csv.writer(outfile,delimiter=',');
        dataWriter.writerow(['# Time     Error        Bytes 1-13']);
        dataWriter.writerow(['#' + description])
        
        self.client.MCPreqstatNormal();
        print "Listening...";
        packetcount = 0;
        starttime = time.time();
        
        while((time.time()-starttime < duration)):
            
            if(faster):
                packet=self.client.fastrxpacket();
            else:
                packet=self.client.rxpacket();
                
            #add the data to list if the pointer was included
            if(data != None):
                #data.append(self.client.packet2parsedstr(packet))
                data.put(self.client.packet2parsedstr(packet))
            if(debug == True):
                #check packet status
                MCPstatusReg = self.client.MCPrxstatus();
                messagestat=MCPstatusReg&0xC0;
                messagetype=MCPstatusReg&0x18;
                if(messagestat == 0xC0):
                    print "Message in both buffers; message type is %02x (0x00 is standard data, 0x08 is standard remote)." %messagetype
                elif(messagestat == 0x80):
                    print "Message in RXB1; message type is %02x (0x00 is standard data, 0x08 is standard remote)." %messagetype
                elif(messagestat == 0x40):
                    print "Message in RXB0; message type is %02x (0x00 is standard data, 0x08 is standard remote)." %messagetype
                elif(messagestat == 0x00):
                    print "No messages in buffers."
            
            if packet!=None:
                
                packetcount+=1;
                row = [];
                row.append("%f"%time.time());
                
                if( verbose==True):
                    #if we want to print a parsed message
                    if( parsed == True):
#                        packetParsed = self.client.packet2parsed(packet)
#                        sId = packetParsed.get('sID')
#                        msg = "sID: %04d" %sId
#                        if( packetParsed.get('eID')):
#                            msg += " eID: %d" %packetParsed.get('eID')
#                        msg += " rtr: %d"%packetParsed['rtr']
#                        length = packetParsed['length']
#                        msg += " length: %d"%length
#                        msg += " data:"
#                        for i in range(0,length):
#                            dbidx = 'db%d'%i
#                            msg +=" %03d"% ord(packetParsed[dbidx])
                        msg = self.client.packet2parsedstr(packet)
                        print msg
                    # if we want to print just the message as it is read off the chip
                    else:
                        print self.client.packet2str(packet)
                
                if(debug == True):
                    
                    #check overflow
                    MCPeflgReg=self.client.peek8(0x2D);
                    print"EFLG register equals: %x" %MCPeflgReg;
                    if((MCPeflgReg & 0xC0)==0xC0):
                        print "WARNING: BOTH overflow flags set. Missed a packet. Clearing and proceeding."
                    elif(MCPeflgReg & 0x80):
                        print "WARNING: RXB1 overflow flag set. A packet has been missed. Clearing and proceeding."
                    elif(MCPeflgReg & 0x40):
                        print "WARNING: RXB0 overflow flag set. A packet has been missed. Clearing and proceeding."
                    self.client.MCPbitmodify(0x2D,0xC0,0x00);
                    print"EFLG register set to: %x" % self.client.peek(0x2D);
                
                    #check for errors
                    if (self.client.peek8(0x2C) & 0x80):
                        self.client.MCPbitmodify(0x2C,0x80,0x00);
                        print "ERROR: Malformed packet recieved: " + self.client.packet2str(packet);
                        row.append(1);
                    else:
                        row.append(0);
                else:
                    row.append(0);  #since we don't check for errors if we're not in debug mode...
                            
                row.append(comment)
                #how long the sniff was for
                row.append(duration)
                #boolean that tells us if there was filtering. 0 == no filters, 1 == filters
                if(standardid != None):
                    row.append(1)
                else:
                    row.append(0)
                #write packet to file
                for byte in packet:
                    row.append("%02x"%ord(byte));
                dataWriter.writerow(row);
        
        outfile.close()
        print "Listened for %d seconds, captured %d packets." %(duration,packetcount);
        return packetcount
        
        
    def filterStdSweep(self, freq, low, high, time = 5):
        msgIDs = []
        self.client.serInit()
        self.client.MCPsetup()
        for i in range(low, high+1, 6):
            print "sniffing id: %d, %d, %d, %d, %d, %d" % (i,i+1,i+2,i+3,i+4,i+5)
            comment= "sweepFilter: "
            #comment = "sweepFilter_%d_%d_%d_%d_%d_%d" % (i,i+1,i+2,i+3,i+4,i+5)
            description = "Running a sweep filer for all the possible standard IDs. This run filters for: %d, %d, %d, %d, %d, %d" % (i,i+1,i+2,i+3,i+4,i+5)
            count = self.sniff(freq=freq, duration = time, description = description,comment = comment, standardid = [i, i+1, i+2, i+3, i+4, i+5])
            if( count != 0):
                for j in range(i,i+5):
                    comment = "sweepFilter: "
                    #comment = "sweepFilter: %d" % (j)
                    description = "Running a sweep filer for all the possible standard IDs. This run filters for: %d " % j
                    count = self.sniff(freq=freq, duration = time, description = description,comment = comment, standardid = [j, j, j, j])
                    if( count != 0):
                        msgIDs.append(j)
        return msgIDs
    
    def sweepRandom(self, freq, number = 5, time = 200):
        msgIDs = []
        ids = []
        self.client.serInit()
        self.client.MCPsetup()
        for i in range(0,number+1,6):
            idsTemp = []
            comment = "sweepFilter: "
            for j in range(0,6,1):
                id = randrange(2047)
                #comment += "_%d" % id
                idsTemp.append(id)
                ids.append(id)
            print comment
            description = "Running a sweep filer for all the possible standard IDs. This runs the following : " + comment
            count = self.sniff(freq=freq, duration=time, description=description, comment = comment, standardid = idsTemp)
            if( count != 0):
                for element in idsTemp:
                    #comment = "sweepFilter: %d" % (element)
                    comment="sweepFilter: "
                    description = "Running a sweep filer for all the possible standard IDs. This run filters for: %d " % element
                    count = self.sniff(freq=freq, duration = time, description = description,comment = comment, standardid = [element, element, element])
                    if( count != 0):
                        msgIDs.append(j)
        return msgIDs, ids
    
    def sniffTest(self, freq):
        
        rate = freq;
        
        print "Calling MCPsetrate for %i." %rate;
        self.client.MCPsetrate(rate);
        self.client.MCPreqstatNormal();
        
        print "Mode: %s" % self.client.MCPcanstatstr();
        print "CNF1: %02x" %self.client.peek8(0x2a);
        print "CNF2: %02x" %self.client.peek8(0x29);
        print "CNF3: %02x\n" %self.client.peek8(0x28);
        
        while(1):
            packet=self.client.rxpacket();
            
            if packet!=None:                
                if (self.client.peek8(0x2C) & 0x80):
                    self.client.MCPbitmodify(0x2C,0x80,0x00);
                    print "malformed packet recieved: "+ self.client.packet2str(packet);
                else:
                    print "properly formatted packet recieved" + self.client.packet2str(packet);
   
    
    def freqtest(self,freq):
        
        self.client.MCPsetup();

        self.client.MCPsetrate(freq);
        self.client.MCPreqstatListenOnly();
    
        print "CAN Freq Test: %3d kHz" %freq;
    
        x = 0;
        errors = 0;
    
        starttime = time.time();
        while((time.time()-starttime < args.time)):
            packet=self.client.rxpacket();
            if packet!=None:
                x+=1;
                
                if (self.client.peek8(0x2C) & 0x80):
                    print "malformed packet recieved"
                    errors+=1;
                    self.client.MCPbitmodify(0x2C,0x80,0x00);
                else:         
                    print self.client.packet2str(packet);
    
        print "Results for %3.1d kHz: recieved %3d packets, registered %3d RX errors." %(freq, x, errors);
    

    def isniff(self,freq):
        """ An intelligent sniffer, decodes message format """
        """ More features to be added soon """
        
        self.client.MCPsetrate(freq);
        self.client.MCPreqstatListenOnly();
        while 1:
            packet=self.client.rxpacket();
            if packet!=None:
                plist=[];
                for byte in packet:
                    plist.append(byte);
                arbid=plist[0:2];
                eid=plist[2:4];
                dlc=plist[4:5];
                data=plist[5:13];         
                print "\nArbID: " + self.client.packet2str(arbid);
                print "EID: " + self.client.packet2str(eid);
                print "DLC: " + self.client.packet2str(dlc);
                print "Data: " + self.client.packet2str(data);

    def test(self):
        
        comm.reset();
        print "Just reset..."
        print "EFLG register:  %02x" % self.client.peek8(0x2d);
        print "Tx Errors:  %3d" % self.client.peek8(0x1c);
        print "Rx Errors:  %3d" % self.client.peek8(0x1d);
        print "CANINTF: %02x"  %self.client.peek8(0x2C);
        self.client.MCPreqstatConfiguration();
        self.client.poke8(0x60,0x66);
        self.client.MCPsetrate(500);
        self.client.MCPreqstatNormal();
        print "In normal mode now"
        print "EFLG register:  %02x" % self.client.peek8(0x2d);
        print "Tx Errors:  %3d" % self.client.peek8(0x1c);
        print "Rx Errors:  %3d" % self.client.peek8(0x1d);
        print "CANINTF: %02x"  %self.client.peek8(0x2C);
        print "Waiting on packets.";
        checkcount = 0;
        packet=None;
        while(1):
            packet=self.client.rxpacket();
            if packet!=None:
                print "Message recieved: %s" % self.client.packet2str(packet);
            else:
                checkcount=checkcount+1;
                if (checkcount%30==0):
                    print "EFLG register:  %02x" % self.client.peek8(0x2d);
                    print "Tx Errors:  %3d" % self.client.peek8(0x1c);
                    print "Rx Errors:  %3d" % self.client.peek8(0x1d);
                    print "CANINTF: %02x"  %self.client.peek8(0x2C);

    
    
    
    def addFilter(self,standardid, verbose= True):
        comment = None
        ### ON-CHIP FILTERING
        if(standardid != None):
            self.client.MCPreqstatConfiguration();  
            self.client.poke8(0x60,0x26); # set RXB0 CTRL register to ONLY accept STANDARD messages with filter match (RXM1=0, RMX0=1, BUKT=1)
            self.client.poke8(0x20,0xFF); #set buffer 0 mask 1 (SID 10:3) to FF
            self.client.poke8(0x21,0xE0); #set buffer 0 mask 2 bits 7:5 (SID 2:0) to 1s
            if(len(standardid)>2):
               self.client.poke8(0x70,0x20); # set RXB1 CTRL register to ONLY accept STANDARD messages with filter match (RXM1=0, RMX0=1)
               self.client.poke8(0x24,0xFF); #set buffer 1 mask 1 (SID 10:3) to FF
               self.client.poke8(0x25,0xE0); #set buffer 1 mask 2 bits 7:5 (SID 2:0) to 1s 
            
            for filter,ID in enumerate(standardid):
        
               if (filter==0):
                RXFSIDH = 0x00;
                RXFSIDL = 0x01;
               elif (filter==1):
                RXFSIDH = 0x04;
                RXFSIDL = 0x05;
               elif (filter==2):
                RXFSIDH = 0x08;
                RXFSIDL = 0x09;
               elif (filter==3):
                RXFSIDH = 0x10;
                RXFSIDL = 0x11;
               elif (filter==4):
                RXFSIDH = 0x14;
                RXFSIDL = 0x15;
               else:
                RXFSIDH = 0x18;
                RXFSIDL = 0x19;
        
               #### split SID into different regs
               SIDlow = (ID & 0x07) << 5;  # get SID bits 2:0, rotate them to bits 7:5
               SIDhigh = (ID >> 3) & 0xFF; # get SID bits 10:3, rotate them to bits 7:0
               
               #write SID to regs 
               self.client.poke8(RXFSIDH,SIDhigh);
               self.client.poke8(RXFSIDL, SIDlow);
        
               if (verbose == True):
                   print "Filtering for SID %d (0x%02xh) with filter #%d"%(ID, ID, filter);
               
        self.client.MCPreqstatNormal();
    
    
    # this will sweep through the given ids to request a packet and then sniff on that
    # id for a given amount duration. This will be repeated the number of attempts time
    
    #at the moment this is set to switch to the next id once  a message is identified
    def rtrSweep(self,freq,lowID,highID, attempts = 1,duration = 1, verbose = True):
        #set up file
        now = datetime.datetime.now()
        datestr = now.strftime("%Y%m%d")
        path = self.DATALOCATION+datestr+"_rtr.csv"
        filename = path
        outfile = open(filename,'a');
        dataWriter = csv.writer(outfile,delimiter=',');
        dataWriter.writerow(['# Time     Error        Bytes 1-13']);
        dataWriter.writerow(['#' + "rtr sweep from %d to %d"%(lowID,highID)])
        print "started"
        #self.client.serInit()
        #self.spitSetup(freq)
        for i in range(lowID,highID+1, 1):
            self.client.serInit()
            self.spitSetup(freq)
            standardid = [i, i, i, i]
            #set filters
            self.addFilter(standardid, verbose = True)
            
            #### split SID into different areas
            SIDlow = (standardid[0] & 0x07) << 5;  # get SID bits 2:0, rotate them to bits 7:5
            SIDhigh = (standardid[0] >> 3) & 0xFF; # get SID bits 10:3, rotate them to bits 7:0
            #create RTR packet
            packet = [SIDhigh, SIDlow, 0x00,0x00,0x40]
            dataWriter.writerow(["#requested id %d"%i])
            #self.client.poke8(0x2C,0x00);  #clear the CANINTF register; we care about bits 0 and 1 (RXnIF flags) which indicate a message is being held 
            #clear buffer
            packet1 = self.client.rxpacket();
            packet2 = self.client.rxpacket();
            #send in rtr request
            self.client.txpacket(packet)
            ## listen for 2 packets. one should be the rtr we requested the other should be
            ## a new packet response
            starttime = time.time()
            while ((time.time() - starttime) < duration):
                packet = self.client.rxpacket()
                if( packet == None):
                    continue
                row = []
                row.append("%f"%time.time()) #timestamp
                row.append(0) #error flag (not checkign)
                row.append("rtrRequest_%d"%i) #comment
                row.append(duration) #sniff time
                row.append(1) # filtering boolean
                for byte in packet:
                    row.append("%02x"%ord(byte));
                dataWriter.writerow(row)
                print self.client.packet2parsedstr(packet)
#            packet1=self.client.rxpacket();
#            packet2=self.client.rxpacket();
#            if( packet1 != None and packet2 != None):
#                print "packets recieved :\n "
#                print self.client.packet2parsedstr(packet1);
#                print self.client.packet2parsedstr(packet2);
#                continue
#            elif( packet1 != None):
#                print self.client.packet2parsedstr(packet1)
#            elif( packet2 != None):
#                print self.client.packet2parsedstr(packet2)
            trial= 2;
            # for each trial
            while( trial <= attempts):
                print "trial: ", trial
                self.client.MCPrts(TXB0=True);
                starttime = time.time()
                # this time we will sniff for the given amount of time to see if there is a
                # time till the packets come in
                while( (time.time()-starttime) < duration):
                    packet=self.client.rxpacket();
                    row = []
                    row.append("%f"%time.time()) #timestamp
                    row.append(0) #error flag (not checking)
                    row.append("rtrRequest_%d"%i) #comment
                    row.append(duration) #sniff time
                    row.append(1) # filtering boolean
                    for byte in packet:
                        row.append("%02x"%ord(byte));
                    dataWriter.writerow(row)
                    print self.client.packet2parsedstr(packet)
#                    packet2=self.client.rxpacket();
#                    
#                    if( packet1 != None and packet2 != None):
#                        print "packets recieved :\n "
#                        print self.client.packet2parsedstr(packet1);
#                        print self.client.packet2parsedstr(packet2);
#                        #break
#                    elif( packet1 != None):
#                        print "just packet1"
#                        print self.client.packet2parsedstr(packet1)
#                    elif( packet2 != None):
#                        print "just packet2"
#                        print self.client.packet2parsedstr(packet2)
                trial += 1
        print "sweep complete"
        outfile.close()
        
    def spitSetup(self,freq):
        self.reset();
        self.client.MCPsetrate(freq);
        self.client.MCPreqstatNormal();
        
    
    def spitSingle(self,freq, standardid, repeat, duration = None, debug = False, packet = None):
        self.spitSetup(freq);
        spit(self,freq, standardid, repeat, duration = None, debug = False, packet = None)

    def spit(self,freq, standardid, repeat, duration = None, debug = False, packet = None):
    

        #### split SID into different regs
        SIDlow = (standardid[0] & 0x07) << 5;  # get SID bits 2:0, rotate them to bits 7:5
        SIDhigh = (standardid[0] >> 3) & 0xFF; # get SID bits 10:3, rotate them to bits 7:0
        
        if(packet == None):
            
            # if no packet, RTR for inputted arbID
            # so packet to transmit is SID + padding out EID registers + RTR request (set bit 6, clear lower nibble of DLC register)
            packet = [SIDhigh, SIDlow, 0x00,0x00,0x40] 
        
        
                #packet = [SIDhigh, SIDlow, 0x00,0x00, # pad out EID regs
                #         0x08, # bit 6 must be set to 0 for data frame (1 for RTR) 
                #        # lower nibble is DLC                   
                #        0x00,0x01,0x02,0x03,0x04,0x05,0x06,0xFF]
        else:

            # if we do have a packet, packet is SID + padding out EID registers + DLC of 8 + packet
            #
            #    TODO: allow for variable-length packets
            #
            packet = [SIDhigh, SIDlow, 0x00,0x00, # pad out EID regs
                  0x08, # bit 6 must be set to 0 for data frame (1 for RTR) 
                  # lower nibble is DLC                   
                 packet[0],packet[1],packet[2],packet[3],packet[4],packet[5],packet[6],packet[7]]
            
        
        if(debug):
            if self.client.MCPcanstat()>>5!=0:
                print "Warning: currently in %s mode. NOT in normal mode! May not transmit.\n" %self.client.MCPcanstatstr();
            print "\nInitial state:"
            print "Tx Errors:  %3d" % self.client.peek8(0x1c);
            print "Rx Errors:  %3d" % self.client.peek8(0x1d);
            print "Error Flags:  %02x\n" % self.client.peek8(0x2d);
            print "TXB0CTRL: %02x" %self.client.peek8(0x30);
            print "CANINTF: %02x\n"  %self.client.peek8(0x2C);
            print "\n\nATTEMPTING TRANSMISSION!!!"
        
                
        print "Transmitting packet: "
        print self.client.packet2str(packet)
                
        self.client.txpacket(packet);
            
        if repeat:
            print "\nNow looping on transmit. "
            if duration!= None:
                starttime = time.time();
                while((time.time()-starttime < duration)):
                    self.client.MCPrts(TXB0=True);
                    print "MSG printed"
            else:
                while(1): 
                    self.client.MCPrts(TXB0=True);
        print "messages injected"
        
        # MORE DEBUGGING        
        if(debug): 
            checkcount = 0;
            TXB0CTRL = self.client.peek8(0x30);
        
            print "Tx Errors:  %3d" % self.client.peek8(0x1c);
            print "Rx Errors:  %3d" % self.client.peek8(0x1d);
            print "EFLG register:  %02x" % self.client.peek8(0x2d);
            print "TXB0CTRL: %02x" %TXB0CTRL;
            print "CANINTF: %02x\n"  %self.client.peek8(0x2C);
        
            while(TXB0CTRL | 0x00 != 0x00):
                checkcount+=1;
                TXB0CTRL = self.client.peek8(0x30);
                if (checkcount %30 ==0):
                    print "Tx Errors:  %3d" % self.client.peek8(0x1c);
                    print "Rx Errors:  %3d" % self.client.peek8(0x1d);
                    print "EFLG register:  %02x" % self.client.peek8(0x2d);
                    print "TXB0CTRL: %02x" %TXB0CTRL;
                    print "CANINTF: %02x\n"  %self.client.peek8(0x2C);


    def setRate(self,freq):
        self.client.MCPsetrate(freq);
        



if __name__ == "__main__":  

    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,description='''\
    
        Run commands on the MCP2515. Valid commands are:
        
            info 
            test
            peek 0x(start) [0x(stop)]
            reset
            
            sniff 
            freqtest
            snifftest
            spit
        ''')
        
    
    parser.add_argument('verb', choices=['info', 'test','peek', 'reset', 'sniff', 'freqtest','snifftest', 'spit']);
    parser.add_argument('-f', '--freq', type=int, default=500, help='The desired frequency (kHz)', choices=[100, 125, 250, 500, 1000]);
    parser.add_argument('-t','--time', type=int, default=15, help='The duration to run the command (s)');
    parser.add_argument('-o', '--output', default=None,help='Output file');
    parser.add_argument("-d", "--description", help='Description of experiment (included in the output file)', default="");
    parser.add_argument('-v',"--verbose",action='store_false',help='-v will stop packet output to terminal', default=True);
    parser.add_argument('-c','--comment', help='Comment attached to ech packet uploaded',default=None);
    parser.add_argument('-b', '--debug', action='store_true', help='-b will turn on debug mode, printing packet status', default=False);
    parser.add_argument('-a', '--standardid', type=int, action='append', help='Standard ID to accept with filter 0 [1, 2, 3, 4, 5]', default=None);
    parser.add_argument('-x', '--faster', action='store_true', help='-x will use "fast packet recieve," which may duplicate packets and/or cause other weird behavior.', default=False);
    parser.add_argument('-r', '--repeat', action='store_true', help='-r with "spit" will continuously send the inputted packet. This will put the GoodTHOPTHER into an infinite loop.', default=False);
    
    
    args = parser.parse_args();
    freq = args.freq
    duration = args.time
    filename = args.output
    description = args.description
    verbose = args.verbose
    comments = args.comment
    debug = args.debug
    standardid = args.standardid
    faster=args.faster
    repeat = args.repeat

    comm = GoodFETMCPCANCommunication();
    
    ##########################
    #   INFO
    ##########################
    #
    # Prints MCP state info
    #
    if(args.verb=="info"):
        comm.printInfo()
        
           
    ##########################
    #   RESET
    ##########################
    #
    #
            
    if(args.verb=="reset"):
        comm.reset()
        
    ##########################
    #   SNIFF
    ##########################
    #
    #   runs in ListenOnly mode
    #   utility function to pull info off the car's CAN bus
    #
    
    if(args.verb=="sniff"):
        comm.sniff(freq=freq,duration=duration,description=description,verbose=verbose,comment=comments,filename=filename, standardid=standardid, debug=debug, faster=faster)    
                    
    ##########################
    #   SNIFF TEST
    ##########################
    #
    #   runs in NORMAL mode
    #   intended for NETWORKED MCP chips to verify proper operation
    #
       
    if(args.verb=="snifftest"):
        comm.sniffTest(freq=freq)
        
        
    ##########################
    #   FREQ TEST
    ##########################
    #
    #   runs in LISTEN ONLY mode
    #   tests bus for desired frequency --> sniffs bus for specified length of time and reports
    #   if packets were properly formatted
    #
    #
    
    if(args.verb=="freqtest"):
        comm.freqtest(freq=freq)



    ##########################
    #   iSniff
    ##########################
    #
    #    """ An intelligent sniffer, decodes message format """
    #    """ More features to be added soon """
    if(args.verb=="isniff"):
        comm.isniff(freq=freq)
                
                
    ##########################
    #   MCP TEST
    ##########################
    #
    #   Runs in LOOPBACK mode
    #   self-check diagnostic
    #   wasn't working before due to improperly formatted packet
    #
    #   ...add automatic packet check rather than making user verify successful packet
    if(args.verb=="test"):
        comm.test()
        
    if(args.verb=="peek"):
        start=0x0000;
        if(len(sys.argv)>2):
            start=int(sys.argv[2],16);
        stop=start;
        if(len(sys.argv)>3):
            stop=int(sys.argv[3],16);
        print "Peeking from %04x to %04x." % (start,stop);
        while start<=stop:
            print "%04x: %02x" % (start,client.peek8(start));
            start=start+1;
            
    ##########################
    #   SPIT
    ##########################
    #
    #   Basic packet transmission
    #   runs in NORMAL MODE!
    # 
    #   checking TX error flags--> currently throwing error flags on every
    #   transmission (travis thinks this is because we're sniffing in listen-only
    #   and thus not generating an ack bit on the recieving board)
    if(args.verb=="spit"):
        comm.spitSingle(freq=freq, standardid=standardid,duration=duration, repeat=repeat, debug=debug)


    
    
    
    
        
        
    
    
    
    
