##################################
## These are production boards.
##################################


ifneq (,$(findstring $(board),goodfet20 goodfet10 goodfet11))
mcu ?= msp430f1612
platform := goodfet
endif

ifneq (,$(findstring $(board),goodfet21))
mcu ?= msp430f2618
platform := goodfet
endif

ifneq (,$(findstring $(board),goodfet30 goodfet31))
mcu ?= msp430f2274
platform := goodfet
# This will link to fit in a '2254, so unneeded packages should be omited.
CONFIG_ccspi = n
endif

ifneq (,$(findstring $(board),goodfet40 goodfet41))
mcu ?= msp430f2618
platform := goodfet
endif

ifneq (,$(findstring $(board),goodfet24))
mcu ?= msp430f2618
platform := goodfet
endif

ifneq (,$(findstring $(board),nhb12b))
mcu ?= msp430f2618
CONFIG_nrf = y
platform := nhb12b
endif

ifneq (,$(findstring $(board),nhb12))
mcu ?= msp430f2618
CONFIG_nrf = y
platform := nhb12
endif

ifneq (,$(findstring $(board),goodfet50 goodfet51))
mcu ?= msp430f5510
platform := goodfet
endif

ifeq ($(board),telosb)
mcu ?= msp430f1611
platform := telosb
config := monitor spi ccspi
CFLAGS += -Duseuart1
endif

ifeq ($(board),telosbbt)
mcu ?=msp430f1612
platform := telosb
config := monitor spi ccspi
endif




##################################
## These are experimental boards.
##################################

ifneq (,$(findstring $(board),donbfet))
GCC := avr-gcc
mcu ?= atmega644p
CFLAGS=$(DEBUG) -mmcu=$(mcu) -W -Os -mcall-prologues -Wall -Wextra -Wuninitialized -fpack-struct -fshort-enums -funsigned-bitfields
config := monitor avr spi jscan
endif

ifneq (,$(findstring $(board),arduino))
GCC := avr-gcc
mcu ?= atmega168
#BSL := avrdude -V -F -c stk500v1 -p m328p -b 57600 -P /dev/tty.usbserial-* -U flash:w:blink.hex
LDFLAGS := 
config := monitor
endif

ifneq (,$(findstring $(board),tilaunchpad))
mcu ?=msp430f1612
CFLAGS := -DDEBUG_LEVEL=3 -DDEBUG_START=1 -DINBAND_DEBUG
CFLAGS+= -Werror -Wall
config := monitor chipcon i2c
endif



mcu ?= undef
ifeq ($(mcu),undef)
$(error Please define board, as explained in the README)
endif
#platform := $(board)

AVAILABLE_APPS = monitor spi jtag sbw jtag430 jtag430x2 i2c jtagarm7 ejtag jtagxscale openocd chipcon avr pic adc nrf ccspi glitch smartcard ps2 slc2 

# defaults
CONFIG_monitor    ?= y
CONFIG_spi        ?= y
CONFIG_jtag       ?= n
CONFIG_sbw        ?= n
CONFIG_jtag430    ?= y
CONFIG_jtag430x2  ?= y
CONFIG_i2c        ?= n
CONFIG_jtagarm7   ?= n
CONFIG_ejtag      ?= n
CONFIG_jtagxscale ?= n
CONFIG_openocd    ?= y
CONFIG_chipcon    ?= y
CONFIG_avr        ?= y
CONFIG_pic        ?= n
CONFIG_adc        ?= n
CONFIG_nrf        ?= n
CONFIG_ccspi      ?= y
CONFIG_glitch     ?= n
CONFIG_smartcard  ?= n
CONFIG_ps2        ?= n
CONFIG_slc2       ?= n

#The CONFIG_foo vars are only interpreted if $(config) is unset.
ifeq ($(config),undef)
config += $(foreach app,$(AVAILABLE_APPS),$(if $(findstring $(CONFIG_$(app)),y yes t true Y YES T TRUE),$(app)))
endif