#ifndef DEFINES_H
#define DEFINES_H

// Power channels...
enum {VDDA1, VDDA2, VDDD1, VDDD2, MAX_SUPPLY_CHANNEL};
enum {CH1, CH2, CH3, CH4, MAX_BI_CHANNEL};

// ----------- CS FPGA - BLOCK RAM ------------------
#define CS_CONFIG_GLOBAL_WRITEMEM		0x0400
#define CS_CONFIG_GLOBAL_READMEM		0x0800
#define CS_CONFIG_PIXEL_WRITEMEM		0x1000
#define CS_CONFIG_PIXEL_READMEM			0x2000

// ----------- CS FPGA - REGISTER -------------------
#define CS_RESET_ALL					0
#define CS_L_STRB						1 // 16-bit register

#define CS_L_LV1						3
#define CS_D_LV1						4
#define CS_QUANTITY						5
#define CS_FREQ							6 // 16-bit register
#define CS_TRIGGER_STRB_LV1				8
#define CS_WRITE_CONFIG_SM				9 // 16-bit register
#define CS_START_CONFIG					11
#define CS_SYSTEM_CONF					12
#define CS_SYNC_LENGTH					13
#define CS_START_SYNC					14
#define CS_INJECTION_NR					15
#define CS_CONFIGURATION_NR				16
#define CS_SELADD0						17
#define CS_SELADD1						18
#define CS_SELADD2						19
#define CS_STATUS_REG					20
#define CS_RESET_SCAN					21
#define CS_SCAN_LED						22
#define CS_POWER_CONTROL				23
#define CS_INMUX_CONTROL				24

#define CS_DOMUX_CONTROL				25 // [1:0] controls data from FE MUX for 4-module adapter card
#define CS_AUXCLK_FREQ					26
#define CS_IREF_PAD_SELECT				27
#define CS_ENABLE_NO_OC					29
#define CS_RESET_NO_OC					30
//#define CS_ENABLE_CMD_LV1				31
//#define CS_SYSTEM_CONF				12
#define CS_RESET_ADD					31
#define CS_SRAM_STATUS					32
#define CS_MEAS_STATUS					33
#define CS_QTY_EVENTS_0					34
#define CS_QTY_EVENTS_1					35
#define CS_QTY_EVENTS_2					36
#define CS_QTY_EVENTS_3					37
#define CS_PS_CONTROL					39
#define CS_START_SYNC_CHECK				40
#define CS_CONTROL_PATTERN				41
#define CS_READ_SYNC_ERRORS_LOW			42
#define CS_READ_SYNC_ERRORS_HIGH		43
#define CS_EVENT_COUNTER				44 // 32-bit register
#define CS_FPGA_COUNT_MODE				48
#define CS_MEASUREMENT_START_STOP		49
#define CS_MEASUREMENT_PAUSE_RESUME		-1 // dummy at the moment
#define CS_HARD_RST_CONTROL				50 // bit 0: Analog rst, bit 1: d1 rst, bit 2: d2 rst
#define CS_CMOS_LINES					51
#define CS_XCK_PHASE_CTRL				52
#define CS_INMUX_IN_CTRL				53 // controls INMUX if INMUX control (bits 5, 4, and 3 of CS_INMUX_CONTROL) are not set to 110 or 111
#define CS_ENABLE_RJ45					54
#define CS_TLU_TRIGGER_DATA_LENGTH		55
#define CS_TLU_TRIGGER_DATA_DELAY		56
#define CS_TRIGGER_RATE_MEAS_0			57 // 32-bit register
#define CS_TRIGGER_RATE_MEAS_1			58
#define CS_TRIGGER_RATE_MEAS_2			59
#define CS_TRIGGER_RATE_MEAS_3			60
#define CS_CABLE_LENGTH					61
#define CS_TRIGGER_MODE					62		// Values: STROBE_SCAN=0, USBPIX_SELF_TRG=1, EXT_TRG=2, TLU_SIMPLE=3, TLU_DATA_HANDSHAKE=4, USBPIX_REPLICATION_SLAVE=5
#define CS_EXT_INPUT_STATE				63
#define CS_BURN_IN_OC_STATE				64 // reg 64 contains the current state of the over current protection of the burn-in card power channels. This register is read-only!
#define CS_EVENT_RATE_MEAS_0			65 // 32-bit register
#define CS_EVENT_RATE_MEAS_1			66
#define CS_EVENT_RATE_MEAS_2			67
#define CS_EVENT_RATE_MEAS_3			68
#define CS_MANCHESTER_ENCODER_CTRL		69


// ----------- uC Commands -------------------
#define CMD_START_SCAN			1
#define CMD_STOP_SCAN			2
#define CMD_GET_SCAN_STATUS		3
#define CMD_GET_ERROR_STATUS	4
#define SCAN_BUSY				0x02
#define SCAN_CANCELED			0x08

// DCS channel defines
//#define CH_VDDA1		1
//#define CH_VDDA2		2
//#define CH_VDDD1		3
//#define CH_VDDD2		4


// FE - command implementaion
#define FE_CMD_NULL          0x000000
//#define FE_REF_RESET         0x000002
//#define FE_SOFT_RESET        0x00000C
#define FE_WRITE_GLOBAL_AB   0xFFFFF1
#define FE_WRITE_GLOBAL_C    0xFFFFF2
#define FE_READ_GLOBAL_AB    0xFFFFF3
#define FE_READ_GLOBAL_C     0xFFFFF4
#define FE_WRITE_SC_DOB      0xFFFFF5
#define FE_WRITE_SC_CMD      0xFFFFF6
#define FE_WRITE_SC_ECL      0xFFFFF7
#define FE_READ_SC_DOB       0xFFFFF8
#define FE_READ_SC_CMD       0xFFFFF9
#define FE_READ_SC_ECL       0xFFFFFA
#define FE_WRITE_GLOBAL      0x001682
#define FE_READ_GLOBAL       0x001681
#define FE_WRITE_PIXEL       0x001684
#define FE_GLOBAL_RESET      0x001688
#define FE_GLOBAL_PULSE      0x001689
#define FE_EN_DATA_TAKE      0x00168A
#define FE_CONF_MODE         0x10168A


#define FE_GLOBAL_RESET      0x001688

// FPGA COUNT MODES
#define FPGA_COUNT_LV1          0x00
#define FPGA_COUNT_DR			0x02
#define FPGA_COUNT_DH			0x01

// scan commands
#define SHIFT_HITBUS			0x01
#define SHIFT_CAP0				0x02
#define SHIFT_CAP1				0x04
#define SHIFT_ENABLE			0x08
#define SHIFT_INVHB			0x10
#define SHIFT_DIGINJ			0x20

// Trigger command
#define FE_LV1_TRIGGER          0x1D

// fast commands
#define FE_BCR                  0x161
#define FE_ECR                  0x162
#define FE_CAL                  0x164

//ADC Identifiers
#define	ADC_GAIN		0
#define	ADC_OFFSET		1
#define	TIA_GAIN		2
#define	N_DUMMY			3
#define	N_MEAN			4

// Command register identifiers
#define ENABLE   0
#define TDAC0  5//1	//TDAC0 is MSB
#define TDAC1  4//2
#define TDAC2  3//3
#define TDAC3  2//4
#define TDAC4  1//5
#define CAP0   6
#define CAP1   7
#define HITBUS 8
#define FDAC0  9
#define FDAC1 10
#define FDAC2 11
#define FDAC3 12
#define DIGINJ 13


//--- Select_xxx multiplexer selects
#define REGCLKIN			  0
#define HITBUS_OUT            1
#define DATA_OUT              3
#define PIXEL_OUT            11
#define GLOBAL_OUT           15


#define COMMAND_REG_SIZE_WO_ADD 14
#define COMMAND_REG_SIZE        24
#define COMMAND_REG_BYTESIZE     3 // #byte command register

#define GLOBAL_REG_SIZE         16

#define CONFIG_REG_DUMMY_ITEMS          5
#define CONFIG_REG_FEI4A_2_ITEMS        7
#define CONFIG_REG_FEI4A_3_ITEMS        5
#define CONFIG_REG_FEI4A_4_ITEMS        5
#define CONFIG_REG_FEI4A_5_ITEMS        6
#define CONFIG_REG_FEI4A_6_ITEMS        6
#define CONFIG_REG_FEI4A_7_ITEMS        6
#define CONFIG_REG_FEI4A_8_ITEMS        6
#define CONFIG_REG_FEI4A_9_ITEMS        6
#define CONFIG_REG_FEI4A_10_ITEMS       6
#define CONFIG_REG_FEI4A_11_ITEMS       6
#define CONFIG_REG_FEI4A_12_ITEMS       6
#define CONFIG_REG_FEI4A_13_ITEMS      20
#define CONFIG_REG_FEI4A_14_ITEMS       6
#define CONFIG_REG_FEI4A_15_ITEMS       6
#define CONFIG_REG_FEI4A_16_ITEMS       6
#define CONFIG_REG_FEI4A_17_ITEMS       6
#define CONFIG_REG_FEI4A_18_ITEMS       6
#define CONFIG_REG_FEI4A_19_ITEMS       6
#define CONFIG_REG_FEI4A_20_ITEMS       6
#define CONFIG_REG_FEI4A_21_ITEMS       9
#define CONFIG_REG_FEI4A_22_ITEMS       8
#define CONFIG_REG_FEI4A_23_ITEMS      20
#define CONFIG_REG_FEI4A_24_ITEMS      20
#define CONFIG_REG_FEI4A_25_ITEMS      13
#define CONFIG_REG_FEI4A_26_ITEMS       7
#define CONFIG_REG_FEI4A_27_ITEMS      16
#define CONFIG_REG_FEI4A_28_ITEMS      16
#define CONFIG_REG_FEI4A_29_ITEMS      12

#define CONFIG_REG_FEI4A_31_ITEMS      10
#define CONFIG_REG_FEI4A_32_ITEMS      20
#define CONFIG_REG_FEI4A_33_ITEMS      20
#define CONFIG_REG_FEI4A_34_ITEMS      14
#define CONFIG_REG_FEI4A_35_ITEMS       5

#define CONFIG_REG_FEI4A_40_ITEMS       5
#define CONFIG_REG_FEI4A_41_ITEMS       6
#define CONFIG_REG_FEI4A_42_ITEMS       5

// FE-I4B register item sizes
#define CONFIG_REG_FEI4B_1_ITEMS        7
#define CONFIG_REG_FEI4B_2_ITEMS        7
#define CONFIG_REG_FEI4B_3_ITEMS        5
#define CONFIG_REG_FEI4B_4_ITEMS        5
#define CONFIG_REG_FEI4B_5_ITEMS        6
#define CONFIG_REG_FEI4B_6_ITEMS        6
#define CONFIG_REG_FEI4B_7_ITEMS        6
#define CONFIG_REG_FEI4B_8_ITEMS        6
#define CONFIG_REG_FEI4B_9_ITEMS        6
#define CONFIG_REG_FEI4B_10_ITEMS       6
#define CONFIG_REG_FEI4B_11_ITEMS       6
#define CONFIG_REG_FEI4B_12_ITEMS       6
#define CONFIG_REG_FEI4B_13_ITEMS      20
#define CONFIG_REG_FEI4B_14_ITEMS       6
#define CONFIG_REG_FEI4B_15_ITEMS       6
#define CONFIG_REG_FEI4B_16_ITEMS       6
#define CONFIG_REG_FEI4B_17_ITEMS       6
#define CONFIG_REG_FEI4B_18_ITEMS       6
#define CONFIG_REG_FEI4B_19_ITEMS       6
#define CONFIG_REG_FEI4B_20_ITEMS       6
#define CONFIG_REG_FEI4B_21_ITEMS       9
#define CONFIG_REG_FEI4B_22_ITEMS       8
#define CONFIG_REG_FEI4B_23_ITEMS      20
#define CONFIG_REG_FEI4B_24_ITEMS      20
#define CONFIG_REG_FEI4B_25_ITEMS      13
#define CONFIG_REG_FEI4B_26_ITEMS       7
#define CONFIG_REG_FEI4B_27_ITEMS      18
#define CONFIG_REG_FEI4B_28_ITEMS      16
#define CONFIG_REG_FEI4B_29_ITEMS      12
#define CONFIG_REG_FEI4B_30_ITEMS      10

#define CONFIG_REG_FEI4B_31_ITEMS      11
#define CONFIG_REG_FEI4B_32_ITEMS      20
#define CONFIG_REG_FEI4B_33_ITEMS      20
#define CONFIG_REG_FEI4B_34_ITEMS      15
#define CONFIG_REG_FEI4B_35_ITEMS       5

#define CONFIG_REG_FEI4B_40_ITEMS       8
#define CONFIG_REG_FEI4B_41_ITEMS       6
#define CONFIG_REG_FEI4B_42_ITEMS       5







#define CONFIG_REG_BITSIZE       40
#define CONFIG_REG_BYTESIZE       5 // #byte command + global register
#define CONF_REG_NUMBER          42 // number of highest conf reg
#define CONFIG_REG_ALL_ITEMS     199 // FIXME: NUMBER OF CONFIG ITEMS
#define PIXEL_REG_ITEMS		     25
#define PIXEL_REG_RB_ITEMS		 21
#define PIXEL_REG_BITSIZE	    696
#define PIXEL_REG_RB_BITSIZE    672
#define PIXEL_REG_BYTESIZE       87 // #byte command + pixel register
#define PIXEL_REG_RB_BYTESIZE    84
#define DC_ITEM_COUNT            21

#define TRIGGER_REG_ITEMS        2
#define TRIGGER_REG_BITSIZE      6
#define TRIGGER_REG_BYTESIZE     1

#define FAST_REG_ITEMS        2
#define FAST_REG_BITSIZE      10
#define FAST_REG_BYTESIZE     2

#define SLOW_REG_ITEMS        4
#define SLOW_REG_BITSIZE     25
#define SLOW_REG_BYTESIZE     4

// Items for FE-I4A bypass cfg
#define SHIFT_REG_AB_A_ITEMS    57
#define SHIFT_REG_C_A_ITEMS     84
// Items for FE-I4B bypass cfg
#define SHIFT_REG_AB_B_ITEMS    57
#define SHIFT_REG_C_B_ITEMS     84
// Hopefully the length of bitstreams stayed the same...
#define SHIFT_REG_AB_BITSIZE   289
#define SHIFT_REG_C_BITSIZE   145
#define SHIFT_REG_AB_BYTESIZE   37
#define SHIFT_REG_C_BYTESIZE   19


#define DCNT_LOAD       2
//#define DCNT_GLOBAL   16
//#define DCNT_PIXEL   672

//Clusterizer definitions
#define __MAXBCID 16			//maximum possible BCID window width
#define __MAXTOTBINS 32			//number of TOT bins for the cluster tot histogram (in TOT = [0:31])
#define __MAXCHARGEBINS 4096	//number of charge bins for the cluster charge histogram (in PlsrDAC)
#define __MAXCLUSTERHITSBINS 32	//number of for the cluster size (=# hits) histogram
#define __MAXPOSXBINS 1000		//number of bins in x for the 2d hit position histogram
#define __MAXPOSYBINS 1000		//number of bins in y for the 2d hit position histogram
#define __PIXELSIZEX 250		//250 um
#define __PIXELSIZEY 50			//50 um

//SRAM identifiers
#define SRAM_BYTESIZE			2097152
#define WORDSIZE				3 // in bytes
#define SRAM_WORDSIZE			SRAM_BYTESIZE/WORDSIZE

// FE-I4A global register identifiers
#define IDLE                    0
#define COMMAND                 1
#define CHIPADDRESS             2
#define REGADDRESS				3
#define FIELD5                500
#define COMMANDDUMMY            4
#define CHIPADDRESSDUMMY        5
#define REGADDRESSDUMMY		    6
#define DUMMY   				7

#define TRIGCNT				    8
#define CONFADDRENABLE		    9
#define CFGSPARE2			   10
#define ERRMASK0			   11
#define ERRMASK1			   12
#define PRMPVBP_R			   13
#define VTHIN				   14
#define DISVBN_CPPM            15
#define PRMPVBP                16
#define TDACVBP                17
#define DISVBN                 18
#define AMP2VBN                19
#define AMP2VBPFOL             20
#define PRMPVBP_T              21
#define AMP2VBP                22
#define FDACVBN                23
#define AMP2VBPFF              24
#define PRMPVBNFOL             25
#define PRMPVBP_L              26
#define PRMPVBPF               27
#define PRMPVBNLCC             28
#define PXSTROBES1             29
#define PXSTROBES0             30
#define PXSTROBE0              31
#define PXSTROBE1              32
#define PXSTROBE2              33
#define PXSTROBE3              34
#define PXSTROBE4              35
#define PXSTROBE5              36
#define PXSTROBE6              37
#define PXSTROBE7              38
#define PXSTROBE8              39
#define PXSTROBE9              40
#define PXSTROBE10             41
#define PXSTROBE11             42
#define PXSTROBE12             43
#define REG13SPARES            44
#define LVDSDRVIREF            45
#define BONNDAC                46
#define PLLIBIAS               47
#define LVDSDRVVOS             48
#define TEMPDENSIBIAS          49
#define PLLICP                 50
#define DAC8SPARE1             51
#define PLSRLDACRAMP           52
#define DAC8SPARE2             53
#define PLSRVGOAMP			   54
#define PLSRDACBIAS			   55
#define DAC8SPARE5             56
#define VTHIN_ALTCOARSE        57
#define VTHIN_ALTFINE          58
#define REG21SPARES            59
#define HITLD_IN               60
#define DINJ_OVERRIDE          61
#define DIGHITIN_SEL           62
#define PLSRDAC                63
#define REG22SPARES2           64
#define COLPR_MODE             65
#define COLPR_ADDR             66
#define REG22SPARES1           67
#define KILLDC15               68
#define KILLDC14               69
#define KILLDC13               70
#define KILLDC12               71
#define KILLDC11               72
#define KILLDC10               73
#define KILLDC9                74
#define KILLDC8                75
#define KILLDC7                76
#define KILLDC6                77
#define KILLDC5                78
#define KILLDC4                79
#define KILLDC3                80
#define KILLDC2                81
#define KILLDC1                82
#define KILLDC0                83
#define KILLDC31               84
#define KILLDC30               85
#define KILLDC29               86
#define KILLDC28               87
#define KILLDC27               88
#define KILLDC26               89
#define KILLDC25               90
#define KILLDC24               91
#define KILLDC23               92
#define KILLDC22               93
#define KILLDC21               94
#define KILLDC20               95
#define KILLDC19               96
#define KILLDC18               97
#define KILLDC17               98
#define KILLDC16               99
#define CHIP_LATENCY          100
#define KILLDC39              101
#define KILLDC38              102
#define KILLDC37              103
#define KILLDC36              104
#define KILLDC35              105
#define KILLDC34              106
#define KILLDC33              107
#define KILLDC32              108
#define CMDCNT0_12            109
#define STOPMODECNFG          110
#define HITDISCCNFG           111
#define ENPLL                 112
#define EFUSE_SENSE           113
#define STOP_CLK              114
#define RD_ERRORS             115
#define RD_SKIPPED            116
#define REG27SPARES           117
#define GATEHITOR             118
#define DIG_INJ               119
#define SR_CLR                120
#define LATCH_EN              121
#define FE_CLK_PULSE          122
#define CMDCNT13              123
#define LVDSDRVSET06          124
#define REG28SPARES           125
#define EN_40M                126
#define EN_80M                127
#define CLK1_S0               128
#define CLK1_S1               129
#define CLK1_S2               130
#define CLK0_S0               131
#define CLK0_S1               132
#define CLK0_S2               133
#define EN_160M               134
#define EN_320M               135
#define REG29SPARES           136
#define DISABLE8B10B		  137
#define CLK2OUTCFG			  138
#define EMPTYRECORD           139
#define REG29SPARE2           140
#define LVDSDRVEN             141
#define LVDSDRVSET30          142
#define LVDSDRVSET12          143
#define RISEUPTAO             144
#define PULSERPWR             145
#define PULSERDELAY           146
#define EXTDIGCALSW           147
#define EXTANCALSW            148
#define REG31SPARES           149
// in SR_C 16 bits are undefined...
#define UNDEFINED             150


/*
#define GPLATCHENABLE         123
#define GPSRCLEAR             124
#define GPEFUSEREAD           125
#define GPREGIONCLK           126
#define GPREGIONSTOPMODE      127
#define GPGADCDIGI            128
#define REG21SPARES           129
#define ANA1SEL               130
#define ANA2SEL               131
#define ANA3SEL               132
#define REG22SPARES           133
#define CMOSOUT0              134
#define CMOSOUT1              135
#define CMOSOUT2              136
#define CMOSOUT3              137
#define ERRMASK0              138
#define ERRMASK1              139
#define ADCSEL                140
#define DCDCCLKDEVIDER        141
#define DCDCCLKPHASE          142
#define REG27SPARES           143
#define CMDCALWIDTH           144
#define CMDCALDELAY           145
#define REG28SPARES           146
#define CMDCALDIGINJ          147
*/
#define EFUSEDC0              150
#define EFUSEDC1              151
#define EFUSEDC2              152
#define EFUSEDC3              153
#define EFUSEDC4              154
#define EFUSEDC5              155
#define EFUSEDC6              156
#define EFUSEDC7              157
#define EFUSEDC8              158
#define EFUSEDC9              159
#define EFUSEDC10             160
#define EFUSEDC11             161
#define EFUSEDC12             162
#define EFUSEDC13             163
#define EFUSEDC14             164
#define EFUSEDC15             165
#define EFUSEDC16             166
#define EFUSEDC17             167
#define EFUSEDC18             168
#define EFUSEDC19             169
#define EFUSEDC20             170
#define EFUSEDC21             171
#define EFUSEDC22             172
#define EFUSEDC23             173
#define EFUSEDC24             174
#define EFUSEDC25             175
#define EFUSEDC26             176
#define EFUSEDC27             177
#define EFUSEDC28             178
#define EFUSEDC29             179
#define EFUSEDC30             180
#define EFUSEDC31             181
#define EFUSEDC32             182
#define EFUSEDC33             183
#define EFUSEDC34             184
#define EFUSEDC35             185
#define EFUSEDC36             186
#define EFUSEDC37             187
#define EFUSEDC38             188
#define EFUSEDC39             189
#define EFUSEVREF             190
#define EFUSECREF             191
#define EFUSECHIPSERNUM       192
#define REG40SPARES           193
#define EOCHLSKIPPED          194
#define REG41SPARES           195
#define READCMDERR            196






// FE-I4B global register identifiers
#define B_IDLE                 1000
#define B_COMMAND              1001
#define B_CHIPADDRESS          1002
#define B_REGADDRESS		   1003
#define B_REG0SPARE			   1004
#define B_REG1SPARE            1005
#define B_SMALLHITERASE		   1006
#define B_EVENTLIMIT           1007
#define B_TRIGCNT			   1008
#define B_CONFADDRENABLE	   1009
#define B_CFGSPARE2			   1010
#define B_ERRMASK0			   1011
#define B_ERRMASK1			   1012
#define B_PRMPVBP_R			   1013
#define B_BUFVGOPAMP		   1014
#define B_REG6SPARE            1015
#define B_PRMPVBP              1016
#define B_TDACVBP              1017
#define B_DISVBN               1018
#define B_AMP2VBN              1019
#define B_AMP2VBPFOL           1020
#define B_REG9SPARE            1021
#define B_AMP2VBP              1022
#define B_FDACVBN              1023
#define B_AMP2VBPFF            1024
#define B_PRMPVBNFOL           1025
#define B_PRMPVBP_L            1026
#define B_PRMPVBPF             1027
#define B_PRMPVBNLCC           1028
#define B_PXSTROBES1           1029
#define B_PXSTROBES0           1030
#define B_PXSTROBE0            1031
#define B_PXSTROBE1            1032
#define B_PXSTROBE2            1033
#define B_PXSTROBE3            1034
#define B_PXSTROBE4            1035
#define B_PXSTROBE5            1036
#define B_PXSTROBE6            1037
#define B_PXSTROBE7            1038
#define B_PXSTROBE8            1039
#define B_PXSTROBE9            1040
#define B_PXSTROBE10           1041
#define B_PXSTROBE11           1042
#define B_PXSTROBE12           1043
#define B_REG13SPARES          1044
#define B_LVDSDRVIREF          1045
#define B_ADCOPAMP             1046
#define B_PLLIBIAS             1047
#define B_LVDSDRVVOS           1048
#define B_TEMPDENSIBIAS        1049
#define B_PLLICP               1050
#define B_DAC8SPARE1           1051
#define B_PLSRLDACRAMP         1052
#define B_VREFDIGTUNE          1053
#define B_PLSRVGOAMP		   1054
#define B_PLSRDACBIAS		   1055
#define B_VREFANTUNE           1056
#define B_VTHIN_ALTCOARSE      1057
#define B_VTHIN_ALTFINE        1058
#define B_REG21SPARES          1059
#define B_HITLD_IN             1060
#define B_DINJ_OVERRIDE        1061
#define B_DIGHITIN_SEL         1062
#define B_PLSRDAC              1063
#define B_REG22SPARES2         1064
#define B_COLPR_MODE           1065
#define B_COLPR_ADDR           1066
#define B_REG22SPARES1         1067
#define B_KILLDC15             1068
#define B_KILLDC14             1069
#define B_KILLDC13             1070
#define B_KILLDC12             1071
#define B_KILLDC11             1072
#define B_KILLDC10             1073
#define B_KILLDC9              1074
#define B_KILLDC8              1075
#define B_KILLDC7              1076
#define B_KILLDC6              1077
#define B_KILLDC5              1078
#define B_KILLDC4              1079
#define B_KILLDC3              1080
#define B_KILLDC2              1081
#define B_KILLDC1              1082
#define B_KILLDC0              1083
#define B_KILLDC31             1084
#define B_KILLDC30             1085
#define B_KILLDC29             1086
#define B_KILLDC28             1087
#define B_KILLDC27             1088
#define B_KILLDC26             1089
#define B_KILLDC25             1090
#define B_KILLDC24             1091
#define B_KILLDC23             1092
#define B_KILLDC22             1093
#define B_KILLDC21             1094
#define B_KILLDC20             1095
#define B_KILLDC19             1096
#define B_KILLDC18             1097
#define B_KILLDC17             1098
#define B_KILLDC16             1099
#define B_CHIP_LATENCY         1100
#define B_KILLDC39             1101
#define B_KILLDC38             1102
#define B_KILLDC37             1103
#define B_KILLDC36             1104
#define B_KILLDC35             1105
#define B_KILLDC34             1106
#define B_KILLDC33             1107
#define B_KILLDC32             1108
#define B_CMDCNT0_12           1109
#define B_STOPMODECNFG         1110
#define B_HITDISCCNFG          1111
#define B_ENPLL                1112
#define B_EFUSE_SENSE          1113
#define B_STOP_CLK             1114
#define B_RD_ERRORS            1115
#define B_REG27SPARE1          1116
#define B_ADC_EN_PULSE         1117
#define B_SR_RD_EN			   1118
#define B_REG27SPARES2		   1119
#define B_GATEHITOR            1120
#define B_DIG_INJ              1121
#define B_SR_CLR               1122
#define B_LATCH_EN             1123
#define B_FE_CLK_PULSE         1124
#define B_CMDCNT13             1125
#define B_LVDSDRVSET06         1126
#define B_REG28SPARES          1127
#define B_EN_40M               1128
#define B_EN_80M               1129
#define B_CLK1_S0              1130
#define B_CLK1_S1              1131
#define B_CLK1_S2              1132
#define B_CLK0_S0              1133
#define B_CLK0_S1              1134
#define B_CLK0_S2              1135
#define B_EN_160M              1136
#define B_EN_320M              1137
#define B_REG29SPARES          1138
#define B_DISABLE8B10B		   1139
#define B_CLK2OUTCFG		   1140
#define B_EMPTYRECORD          1141
#define B_REG29SPARE2          1142
#define B_LVDSDRVEN            1143
#define B_LVDSDRVSET30         1144
#define B_LVDSDRVSET12         1145
#define B_TMPSENSED0		   1146
#define B_TMPSENSED1		   1147
#define B_TMPSENSEDISABLE	   1148
#define B_ILEAKRANGE		   1149
#define B_REG30SPARES		   1150
#define B_RISEUPTAO            1151
#define B_PULSERPWR            1152
#define B_PULSERDELAY          1153
#define B_EXTDIGCALSW          1154
#define B_EXTANCALSW           1155
#define B_REG31SPARES          1156
#define B_ADCSELECT            1157
#define B_EFUSEDC0             1158
#define B_EFUSEDC1             1159
#define B_EFUSEDC2             1160
#define B_EFUSEDC3             1161
#define B_EFUSEDC4             1162
#define B_EFUSEDC5             1163
#define B_EFUSEDC6             1164
#define B_EFUSEDC7             1165
#define B_EFUSEDC8             1166
#define B_EFUSEDC9             1167
#define B_EFUSEDC10            1168
#define B_EFUSEDC11            1169
#define B_EFUSEDC12            1170
#define B_EFUSEDC13            1171
#define B_EFUSEDC14            1172
#define B_EFUSEDC15            1173
#define B_EFUSEDC16            1174
#define B_EFUSEDC17            1175
#define B_EFUSEDC18            1176
#define B_EFUSEDC19            1177
#define B_EFUSEDC20            1178
#define B_EFUSEDC21            1179
#define B_EFUSEDC22            1180
#define B_EFUSEDC23            1181
#define B_EFUSEDC24            1182
#define B_EFUSEDC25            1183
#define B_EFUSEDC26            1184
#define B_EFUSEDC27            1185
#define B_EFUSEDC28            1186
#define B_EFUSEDC29            1187
#define B_EFUSEDC30            1188
#define B_EFUSEDC31            1189
#define B_EFUSEDC32            1190
#define B_EFUSEDC33            1191
#define B_EFUSEDC34            1192
#define B_EFUSEDC35            1193
#define B_EFUSEDC36            1194
#define B_EFUSEDC37            1195
#define B_EFUSEDC38            1196
#define B_EFUSEDC39            1197
#define B_REG34SPARES1		   1198
#define B_PRMPVBPMSNEN		   1199
#define B_REG34SPARES2		   1200
#define B_EFUSECHIPSERNUM      1201
#define B_REG40SPARES          1202
#define B_GADCOUT              1203
#define B_GADCSTATUS           1204
#define B_GADCSELECTRB         1205
#define B_EOCHLSKIPPED         1206
#define B_REG41SPARES          1207
#define B_READCMDERR           1208




















#define DUMMY1					0
#define DUMMY2					1
#define DUMMY3					2
#define DUMMY4					3
#define DUMMY5					4

// pixel register identifiers
#define PIXEL26880			4
#define PIXEL26848			5
#define PIXEL26816			6
#define PIXEL26784			7
#define PIXEL26752			8
#define PIXEL26720			9
#define PIXEL26688			10
#define PIXEL26656			11
#define PIXEL26624			12
#define PIXEL26592			13
#define PIXEL26560			14
#define PIXEL26528			15
#define PIXEL26496			16
#define PIXEL26464			17
#define PIXEL26432			18
#define PIXEL26400			19
#define PIXEL26368			20
#define PIXEL26336			21
#define PIXEL26304			22
#define PIXEL26272			23
#define PIXEL26240			24
#define PIXEL26208			25
#define PIXEL26176			26
#define PIXEL26144			27
#define PIXEL26112			28
#define PIXEL26080			29
#define PIXEL26048			30
#define PIXEL26016			31
#define PIXEL25984			32
#define PIXEL25952			33
#define PIXEL25920			34
#define PIXEL25888			35
#define PIXEL25856			36
#define PIXEL25824			37
#define PIXEL25792			38
#define PIXEL25760			39
#define PIXEL25728			40
#define PIXEL25696			41
#define PIXEL25664			42
#define PIXEL25632			43
#define PIXEL25600			44
#define PIXEL25568			45
#define PIXEL25536			46
#define PIXEL25504			47
#define PIXEL25472			48
#define PIXEL25440			49
#define PIXEL25408			50
#define PIXEL25376			51
#define PIXEL25344			52
#define PIXEL25312			53
#define PIXEL25280			54
#define PIXEL25248			55
#define PIXEL25216			56
#define PIXEL25184			57
#define PIXEL25152			58
#define PIXEL25120			59
#define PIXEL25088			60
#define PIXEL25056			61
#define PIXEL25024			62
#define PIXEL24992			63
#define PIXEL24960			64
#define PIXEL24928			65
#define PIXEL24896			66
#define PIXEL24864			67
#define PIXEL24832			68
#define PIXEL24800			69
#define PIXEL24768			70
#define PIXEL24736			71
#define PIXEL24704			72
#define PIXEL24672			73
#define PIXEL24640			74
#define PIXEL24608			75
#define PIXEL24576			76
#define PIXEL24544			77
#define PIXEL24512			78
#define PIXEL24480			79
#define PIXEL24448			80
#define PIXEL24416			81
#define PIXEL24384			82
#define PIXEL24352			83
#define PIXEL24320			84
#define PIXEL24288			85
#define PIXEL24256			86
#define PIXEL24224			87
#define PIXEL24192			88
#define PIXEL24160			89
#define PIXEL24128			90
#define PIXEL24096			91
#define PIXEL24064			92
#define PIXEL24032			93
#define PIXEL24000			94
#define PIXEL23968			95
#define PIXEL23936			96
#define PIXEL23904			97
#define PIXEL23872			98
#define PIXEL23840			99
#define PIXEL23808			100
#define PIXEL23776			101
#define PIXEL23744			102
#define PIXEL23712			103
#define PIXEL23680			104
#define PIXEL23648			105
#define PIXEL23616			106
#define PIXEL23584			107
#define PIXEL23552			108
#define PIXEL23520			109
#define PIXEL23488			110
#define PIXEL23456			111
#define PIXEL23424			112
#define PIXEL23392			113
#define PIXEL23360			114
#define PIXEL23328			115
#define PIXEL23296			116
#define PIXEL23264			117
#define PIXEL23232			118
#define PIXEL23200			119
#define PIXEL23168			120
#define PIXEL23136			121
#define PIXEL23104			122
#define PIXEL23072			123
#define PIXEL23040			124
#define PIXEL23008			125
#define PIXEL22976			126
#define PIXEL22944			127
#define PIXEL22912			128
#define PIXEL22880			129
#define PIXEL22848			130
#define PIXEL22816			131
#define PIXEL22784			132
#define PIXEL22752			133
#define PIXEL22720			134
#define PIXEL22688			135
#define PIXEL22656			136
#define PIXEL22624			137
#define PIXEL22592			138
#define PIXEL22560			139
#define PIXEL22528			140
#define PIXEL22496			141
#define PIXEL22464			142
#define PIXEL22432			143
#define PIXEL22400			144
#define PIXEL22368			145
#define PIXEL22336			146
#define PIXEL22304			147
#define PIXEL22272			148
#define PIXEL22240			149
#define PIXEL22208			150
#define PIXEL22176			151
#define PIXEL22144			152
#define PIXEL22112			153
#define PIXEL22080			154
#define PIXEL22048			155
#define PIXEL22016			156
#define PIXEL21984			157
#define PIXEL21952			158
#define PIXEL21920			159
#define PIXEL21888			160
#define PIXEL21856			161
#define PIXEL21824			162
#define PIXEL21792			163
#define PIXEL21760			164
#define PIXEL21728			165
#define PIXEL21696			166
#define PIXEL21664			167
#define PIXEL21632			168
#define PIXEL21600			169
#define PIXEL21568			170
#define PIXEL21536			171
#define PIXEL21504			172
#define PIXEL21472			173
#define PIXEL21440			174
#define PIXEL21408			175
#define PIXEL21376			176
#define PIXEL21344			177
#define PIXEL21312			178
#define PIXEL21280			179
#define PIXEL21248			180
#define PIXEL21216			181
#define PIXEL21184			182
#define PIXEL21152			183
#define PIXEL21120			184
#define PIXEL21088			185
#define PIXEL21056			186
#define PIXEL21024			187
#define PIXEL20992			188
#define PIXEL20960			189
#define PIXEL20928			190
#define PIXEL20896			191
#define PIXEL20864			192
#define PIXEL20832			193
#define PIXEL20800			194
#define PIXEL20768			195
#define PIXEL20736			196
#define PIXEL20704			197
#define PIXEL20672			198
#define PIXEL20640			199
#define PIXEL20608			200
#define PIXEL20576			201
#define PIXEL20544			202
#define PIXEL20512			203
#define PIXEL20480			204
#define PIXEL20448			205
#define PIXEL20416			206
#define PIXEL20384			207
#define PIXEL20352			208
#define PIXEL20320			209
#define PIXEL20288			210
#define PIXEL20256			211
#define PIXEL20224			212
#define PIXEL20192			213
#define PIXEL20160			214
#define PIXEL20128			215
#define PIXEL20096			216
#define PIXEL20064			217
#define PIXEL20032			218
#define PIXEL20000			219
#define PIXEL19968			220
#define PIXEL19936			221
#define PIXEL19904			222
#define PIXEL19872			223
#define PIXEL19840			224
#define PIXEL19808			225
#define PIXEL19776			226
#define PIXEL19744			227
#define PIXEL19712			228
#define PIXEL19680			229
#define PIXEL19648			230
#define PIXEL19616			231
#define PIXEL19584			232
#define PIXEL19552			233
#define PIXEL19520			234
#define PIXEL19488			235
#define PIXEL19456			236
#define PIXEL19424			237
#define PIXEL19392			238
#define PIXEL19360			239
#define PIXEL19328			240
#define PIXEL19296			241
#define PIXEL19264			242
#define PIXEL19232			243
#define PIXEL19200			244
#define PIXEL19168			245
#define PIXEL19136			246
#define PIXEL19104			247
#define PIXEL19072			248
#define PIXEL19040			249
#define PIXEL19008			250
#define PIXEL18976			251
#define PIXEL18944			252
#define PIXEL18912			253
#define PIXEL18880			254
#define PIXEL18848			255
#define PIXEL18816			256
#define PIXEL18784			257
#define PIXEL18752			258
#define PIXEL18720			259
#define PIXEL18688			260
#define PIXEL18656			261
#define PIXEL18624			262
#define PIXEL18592			263
#define PIXEL18560			264
#define PIXEL18528			265
#define PIXEL18496			266
#define PIXEL18464			267
#define PIXEL18432			268
#define PIXEL18400			269
#define PIXEL18368			270
#define PIXEL18336			271
#define PIXEL18304			272
#define PIXEL18272			273
#define PIXEL18240			274
#define PIXEL18208			275
#define PIXEL18176			276
#define PIXEL18144			277
#define PIXEL18112			278
#define PIXEL18080			279
#define PIXEL18048			280
#define PIXEL18016			281
#define PIXEL17984			282
#define PIXEL17952			283
#define PIXEL17920			284
#define PIXEL17888			285
#define PIXEL17856			286
#define PIXEL17824			287
#define PIXEL17792			288
#define PIXEL17760			289
#define PIXEL17728			290
#define PIXEL17696			291
#define PIXEL17664			292
#define PIXEL17632			293
#define PIXEL17600			294
#define PIXEL17568			295
#define PIXEL17536			296
#define PIXEL17504			297
#define PIXEL17472			298
#define PIXEL17440			299
#define PIXEL17408			300
#define PIXEL17376			301
#define PIXEL17344			302
#define PIXEL17312			303
#define PIXEL17280			304
#define PIXEL17248			305
#define PIXEL17216			306
#define PIXEL17184			307
#define PIXEL17152			308
#define PIXEL17120			309
#define PIXEL17088			310
#define PIXEL17056			311
#define PIXEL17024			312
#define PIXEL16992			313
#define PIXEL16960			314
#define PIXEL16928			315
#define PIXEL16896			316
#define PIXEL16864			317
#define PIXEL16832			318
#define PIXEL16800			319
#define PIXEL16768			320
#define PIXEL16736			321
#define PIXEL16704			322
#define PIXEL16672			323
#define PIXEL16640			324
#define PIXEL16608			325
#define PIXEL16576			326
#define PIXEL16544			327
#define PIXEL16512			328
#define PIXEL16480			329
#define PIXEL16448			330
#define PIXEL16416			331
#define PIXEL16384			332
#define PIXEL16352			333
#define PIXEL16320			334
#define PIXEL16288			335
#define PIXEL16256			336
#define PIXEL16224			337
#define PIXEL16192			338
#define PIXEL16160			339
#define PIXEL16128			340
#define PIXEL16096			341
#define PIXEL16064			342
#define PIXEL16032			343
#define PIXEL16000			344
#define PIXEL15968			345
#define PIXEL15936			346
#define PIXEL15904			347
#define PIXEL15872			348
#define PIXEL15840			349
#define PIXEL15808			350
#define PIXEL15776			351
#define PIXEL15744			352
#define PIXEL15712			353
#define PIXEL15680			354
#define PIXEL15648			355
#define PIXEL15616			356
#define PIXEL15584			357
#define PIXEL15552			358
#define PIXEL15520			359
#define PIXEL15488			360
#define PIXEL15456			361
#define PIXEL15424			362
#define PIXEL15392			363
#define PIXEL15360			364
#define PIXEL15328			365
#define PIXEL15296			366
#define PIXEL15264			367
#define PIXEL15232			368
#define PIXEL15200			369
#define PIXEL15168			370
#define PIXEL15136			371
#define PIXEL15104			372
#define PIXEL15072			373
#define PIXEL15040			374
#define PIXEL15008			375
#define PIXEL14976			376
#define PIXEL14944			377
#define PIXEL14912			378
#define PIXEL14880			379
#define PIXEL14848			380
#define PIXEL14816			381
#define PIXEL14784			382
#define PIXEL14752			383
#define PIXEL14720			384
#define PIXEL14688			385
#define PIXEL14656			386
#define PIXEL14624			387
#define PIXEL14592			388
#define PIXEL14560			389
#define PIXEL14528			390
#define PIXEL14496			391
#define PIXEL14464			392
#define PIXEL14432			393
#define PIXEL14400			394
#define PIXEL14368			395
#define PIXEL14336			396
#define PIXEL14304			397
#define PIXEL14272			398
#define PIXEL14240			399
#define PIXEL14208			400
#define PIXEL14176			401
#define PIXEL14144			402
#define PIXEL14112			403
#define PIXEL14080			404
#define PIXEL14048			405
#define PIXEL14016			406
#define PIXEL13984			407
#define PIXEL13952			408
#define PIXEL13920			409
#define PIXEL13888			410
#define PIXEL13856			411
#define PIXEL13824			412
#define PIXEL13792			413
#define PIXEL13760			414
#define PIXEL13728			415
#define PIXEL13696			416
#define PIXEL13664			417
#define PIXEL13632			418
#define PIXEL13600			419
#define PIXEL13568			420
#define PIXEL13536			421
#define PIXEL13504			422
#define PIXEL13472			423
#define PIXEL13440			424
#define PIXEL13408			425
#define PIXEL13376			426
#define PIXEL13344			427
#define PIXEL13312			428
#define PIXEL13280			429
#define PIXEL13248			430
#define PIXEL13216			431
#define PIXEL13184			432
#define PIXEL13152			433
#define PIXEL13120			434
#define PIXEL13088			435
#define PIXEL13056			436
#define PIXEL13024			437
#define PIXEL12992			438
#define PIXEL12960			439
#define PIXEL12928			440
#define PIXEL12896			441
#define PIXEL12864			442
#define PIXEL12832			443
#define PIXEL12800			444
#define PIXEL12768			445
#define PIXEL12736			446
#define PIXEL12704			447
#define PIXEL12672			448
#define PIXEL12640			449
#define PIXEL12608			450
#define PIXEL12576			451
#define PIXEL12544			452
#define PIXEL12512			453
#define PIXEL12480			454
#define PIXEL12448			455
#define PIXEL12416			456
#define PIXEL12384			457
#define PIXEL12352			458
#define PIXEL12320			459
#define PIXEL12288			460
#define PIXEL12256			461
#define PIXEL12224			462
#define PIXEL12192			463
#define PIXEL12160			464
#define PIXEL12128			465
#define PIXEL12096			466
#define PIXEL12064			467
#define PIXEL12032			468
#define PIXEL12000			469
#define PIXEL11968			470
#define PIXEL11936			471
#define PIXEL11904			472
#define PIXEL11872			473
#define PIXEL11840			474
#define PIXEL11808			475
#define PIXEL11776			476
#define PIXEL11744			477
#define PIXEL11712			478
#define PIXEL11680			479
#define PIXEL11648			480
#define PIXEL11616			481
#define PIXEL11584			482
#define PIXEL11552			483
#define PIXEL11520			484
#define PIXEL11488			485
#define PIXEL11456			486
#define PIXEL11424			487
#define PIXEL11392			488
#define PIXEL11360			489
#define PIXEL11328			490
#define PIXEL11296			491
#define PIXEL11264			492
#define PIXEL11232			493
#define PIXEL11200			494
#define PIXEL11168			495
#define PIXEL11136			496
#define PIXEL11104			497
#define PIXEL11072			498
#define PIXEL11040			499
#define PIXEL11008			500
#define PIXEL10976			501
#define PIXEL10944			502
#define PIXEL10912			503
#define PIXEL10880			504
#define PIXEL10848			505
#define PIXEL10816			506
#define PIXEL10784			507
#define PIXEL10752			508
#define PIXEL10720			509
#define PIXEL10688			510
#define PIXEL10656			511
#define PIXEL10624			512
#define PIXEL10592			513
#define PIXEL10560			514
#define PIXEL10528			515
#define PIXEL10496			516
#define PIXEL10464			517
#define PIXEL10432			518
#define PIXEL10400			519
#define PIXEL10368			520
#define PIXEL10336			521
#define PIXEL10304			522
#define PIXEL10272			523
#define PIXEL10240			524
#define PIXEL10208			525
#define PIXEL10176			526
#define PIXEL10144			527
#define PIXEL10112			528
#define PIXEL10080			529
#define PIXEL10048			530
#define PIXEL10016			531
#define PIXEL9984			532
#define PIXEL9952			533
#define PIXEL9920			534
#define PIXEL9888			535
#define PIXEL9856			536
#define PIXEL9824			537
#define PIXEL9792			538
#define PIXEL9760			539
#define PIXEL9728			540
#define PIXEL9696			541
#define PIXEL9664			542
#define PIXEL9632			543
#define PIXEL9600			544
#define PIXEL9568			545
#define PIXEL9536			546
#define PIXEL9504			547
#define PIXEL9472			548
#define PIXEL9440			549
#define PIXEL9408			550
#define PIXEL9376			551
#define PIXEL9344			552
#define PIXEL9312			553
#define PIXEL9280			554
#define PIXEL9248			555
#define PIXEL9216			556
#define PIXEL9184			557
#define PIXEL9152			558
#define PIXEL9120			559
#define PIXEL9088			560
#define PIXEL9056			561
#define PIXEL9024			562
#define PIXEL8992			563
#define PIXEL8960			564
#define PIXEL8928			565
#define PIXEL8896			566
#define PIXEL8864			567
#define PIXEL8832			568
#define PIXEL8800			569
#define PIXEL8768			570
#define PIXEL8736			571
#define PIXEL8704			572
#define PIXEL8672			573
#define PIXEL8640			574
#define PIXEL8608			575
#define PIXEL8576			576
#define PIXEL8544			577
#define PIXEL8512			578
#define PIXEL8480			579
#define PIXEL8448			580
#define PIXEL8416			581
#define PIXEL8384			582
#define PIXEL8352			583
#define PIXEL8320			584
#define PIXEL8288			585
#define PIXEL8256			586
#define PIXEL8224			587
#define PIXEL8192			588
#define PIXEL8160			589
#define PIXEL8128			590
#define PIXEL8096			591
#define PIXEL8064			592
#define PIXEL8032			593
#define PIXEL8000			594
#define PIXEL7968			595
#define PIXEL7936			596
#define PIXEL7904			597
#define PIXEL7872			598
#define PIXEL7840			599
#define PIXEL7808			600
#define PIXEL7776			601
#define PIXEL7744			602
#define PIXEL7712			603
#define PIXEL7680			604
#define PIXEL7648			605
#define PIXEL7616			606
#define PIXEL7584			607
#define PIXEL7552			608
#define PIXEL7520			609
#define PIXEL7488			610
#define PIXEL7456			611
#define PIXEL7424			612
#define PIXEL7392			613
#define PIXEL7360			614
#define PIXEL7328			615
#define PIXEL7296			616
#define PIXEL7264			617
#define PIXEL7232			618
#define PIXEL7200			619
#define PIXEL7168			620
#define PIXEL7136			621
#define PIXEL7104			622
#define PIXEL7072			623
#define PIXEL7040			624
#define PIXEL7008			625
#define PIXEL6976			626
#define PIXEL6944			627
#define PIXEL6912			628
#define PIXEL6880			629
#define PIXEL6848			630
#define PIXEL6816			631
#define PIXEL6784			632
#define PIXEL6752			633
#define PIXEL6720			634
#define PIXEL6688			635
#define PIXEL6656			636
#define PIXEL6624			637
#define PIXEL6592			638
#define PIXEL6560			639
#define PIXEL6528			640
#define PIXEL6496			641
#define PIXEL6464			642
#define PIXEL6432			643
#define PIXEL6400			644
#define PIXEL6368			645
#define PIXEL6336			646
#define PIXEL6304			647
#define PIXEL6272			648
#define PIXEL6240			649
#define PIXEL6208			650
#define PIXEL6176			651
#define PIXEL6144			652
#define PIXEL6112			653
#define PIXEL6080			654
#define PIXEL6048			655
#define PIXEL6016			656
#define PIXEL5984			657
#define PIXEL5952			658
#define PIXEL5920			659
#define PIXEL5888			660
#define PIXEL5856			661
#define PIXEL5824			662
#define PIXEL5792			663
#define PIXEL5760			664
#define PIXEL5728			665
#define PIXEL5696			666
#define PIXEL5664			667
#define PIXEL5632			668
#define PIXEL5600			669
#define PIXEL5568			670
#define PIXEL5536			671
#define PIXEL5504			672
#define PIXEL5472			673
#define PIXEL5440			674
#define PIXEL5408			675
#define PIXEL5376			676
#define PIXEL5344			677
#define PIXEL5312			678
#define PIXEL5280			679
#define PIXEL5248			680
#define PIXEL5216			681
#define PIXEL5184			682
#define PIXEL5152			683
#define PIXEL5120			684
#define PIXEL5088			685
#define PIXEL5056			686
#define PIXEL5024			687
#define PIXEL4992			688
#define PIXEL4960			689
#define PIXEL4928			690
#define PIXEL4896			691
#define PIXEL4864			692
#define PIXEL4832			693
#define PIXEL4800			694
#define PIXEL4768			695
#define PIXEL4736			696
#define PIXEL4704			697
#define PIXEL4672			698
#define PIXEL4640			699
#define PIXEL4608			700
#define PIXEL4576			701
#define PIXEL4544			702
#define PIXEL4512			703
#define PIXEL4480			704
#define PIXEL4448			705
#define PIXEL4416			706
#define PIXEL4384			707
#define PIXEL4352			708
#define PIXEL4320			709
#define PIXEL4288			710
#define PIXEL4256			711
#define PIXEL4224			712
#define PIXEL4192			713
#define PIXEL4160			714
#define PIXEL4128			715
#define PIXEL4096			716
#define PIXEL4064			717
#define PIXEL4032			718
#define PIXEL4000			719
#define PIXEL3968			720
#define PIXEL3936			721
#define PIXEL3904			722
#define PIXEL3872			723
#define PIXEL3840			724
#define PIXEL3808			725
#define PIXEL3776			726
#define PIXEL3744			727
#define PIXEL3712			728
#define PIXEL3680			729
#define PIXEL3648			730
#define PIXEL3616			731
#define PIXEL3584			732
#define PIXEL3552			733
#define PIXEL3520			734
#define PIXEL3488			735
#define PIXEL3456			736
#define PIXEL3424			737
#define PIXEL3392			738
#define PIXEL3360			739
#define PIXEL3328			740
#define PIXEL3296			741
#define PIXEL3264			742
#define PIXEL3232			743
#define PIXEL3200			744
#define PIXEL3168			745
#define PIXEL3136			746
#define PIXEL3104			747
#define PIXEL3072			748
#define PIXEL3040			749
#define PIXEL3008			750
#define PIXEL2976			751
#define PIXEL2944			752
#define PIXEL2912			753
#define PIXEL2880			754
#define PIXEL2848			755
#define PIXEL2816			756
#define PIXEL2784			757
#define PIXEL2752			758
#define PIXEL2720			759
#define PIXEL2688			760
#define PIXEL2656			761
#define PIXEL2624			762
#define PIXEL2592			763
#define PIXEL2560			764
#define PIXEL2528			765
#define PIXEL2496			766
#define PIXEL2464			767
#define PIXEL2432			768
#define PIXEL2400			769
#define PIXEL2368			770
#define PIXEL2336			771
#define PIXEL2304			772
#define PIXEL2272			773
#define PIXEL2240			774
#define PIXEL2208			775
#define PIXEL2176			776
#define PIXEL2144			777
#define PIXEL2112			778
#define PIXEL2080			779
#define PIXEL2048			780
#define PIXEL2016			781
#define PIXEL1984			782
#define PIXEL1952			783
#define PIXEL1920			784
#define PIXEL1888			785
#define PIXEL1856			786
#define PIXEL1824			787
#define PIXEL1792			788
#define PIXEL1760			789
#define PIXEL1728			790
#define PIXEL1696			791
#define PIXEL1664			792
#define PIXEL1632			793
#define PIXEL1600			794
#define PIXEL1568			795
#define PIXEL1536			796
#define PIXEL1504			797
#define PIXEL1472			798
#define PIXEL1440			799
#define PIXEL1408			800
#define PIXEL1376			801
#define PIXEL1344			802
#define PIXEL1312			803
#define PIXEL1280			804
#define PIXEL1248			805
#define PIXEL1216			806
#define PIXEL1184			807
#define PIXEL1152			808
#define PIXEL1120			809
#define PIXEL1088			810
#define PIXEL1056			811
#define PIXEL1024			812
#define PIXEL992			813
#define PIXEL960			814
#define PIXEL928			815
#define PIXEL896			816
#define PIXEL864			817
#define PIXEL832			818
#define PIXEL800			819
#define PIXEL768			820
#define PIXEL736			821
#define PIXEL704			822
#define PIXEL672			823
#define PIXEL640			824
#define PIXEL608			825
#define PIXEL576			826
#define PIXEL544			827
#define PIXEL512			828
#define PIXEL480			829
#define PIXEL448			830
#define PIXEL416			831
#define PIXEL384			832
#define PIXEL352			833
#define PIXEL320			834
#define PIXEL288			835
#define PIXEL256			836
#define PIXEL224			837
#define PIXEL192			838
#define PIXEL160			839
#define PIXEL128			840
#define PIXEL96				841
#define PIXEL64				842
#define PIXEL32				843

// Scan chain
#define SC_DOB					1
#define SC_CMD					2
#define SC_ECL					3

#define SC_DOB_ITEMS			3//4
#define SC_DOB_BITSIZE			72
#define SC_DOB_BYTESIZE			9

#define SC_CMD_ITEMS			9
#define SC_CMD_BITSIZE			262//231
#define SC_CMD_BYTESIZE			33

#define SC_ECL_A_ITEMS			100
#define SC_ECL_A_BITSIZE		3192
#define SC_ECL_A_BYTESIZE		399

#define SC_ECL_B_ITEMS			109
#define SC_ECL_B_BITSIZE		3470
#define SC_ECL_B_BYTESIZE		434

// Data output block
#define SCDOB0			1
#define SCDOB1			2
#define SCDOB2			3
// Command decoder
#define SCCMD0			1
#define SCCMD1			2
#define SCCMD2			3
#define SCCMD3			4
#define SCCMD4			5
#define SCCMD5			6
#define SCCMD6			7
#define SCCMD7			8
#define SCCMD8			9

//End of chip logic
#define	SCECL0			1
#define	SCECL1			2
#define	SCECL2			3
#define	SCECL3			4
#define	SCECL4			5
#define	SCECL5			6
#define	SCECL6			7
#define	SCECL7			8
#define	SCECL8			9
#define	SCECL9			10
#define	SCECL10			11
#define	SCECL11			12
#define	SCECL12			13
#define	SCECL13			14
#define	SCECL14			15
#define	SCECL15			16
#define	SCECL16			17
#define	SCECL17			18
#define	SCECL18			19
#define	SCECL19			20
#define	SCECL20			21
#define	SCECL21			22
#define	SCECL22			23
#define	SCECL23			24
#define	SCECL24			25
#define	SCECL25			26
#define	SCECL26			27
#define	SCECL27			28
#define	SCECL28			29
#define	SCECL29			30
#define	SCECL30			31
#define	SCECL31			32
#define	SCECL32			33
#define	SCECL33			34
#define	SCECL34			35
#define	SCECL35			36
#define	SCECL36			37
#define	SCECL37			38
#define	SCECL38			39
#define	SCECL39			40
#define	SCECL40			41
#define	SCECL41			42
#define	SCECL42			43
#define	SCECL43			44
#define	SCECL44			45
#define	SCECL45			46
#define	SCECL46			47
#define	SCECL47			48
#define	SCECL48			49
#define	SCECL49			50
#define	SCECL50			51
#define	SCECL51			52
#define	SCECL52			53
#define	SCECL53			54
#define	SCECL54			55
#define	SCECL55			56
#define	SCECL56			57
#define	SCECL57			58
#define	SCECL58			59
#define	SCECL59			60
#define	SCECL60			61
#define	SCECL61			62
#define	SCECL62			63
#define	SCECL63			64
#define	SCECL64			65
#define	SCECL65			66
#define	SCECL66			67
#define	SCECL67			68
#define	SCECL68			69
#define	SCECL69			70
#define	SCECL70			71
#define	SCECL71			72
#define	SCECL72			73
#define	SCECL73			74
#define	SCECL74			75
#define	SCECL75			76
#define	SCECL76			77
#define	SCECL77			78
#define	SCECL78			79
#define	SCECL79			80
#define	SCECL80			81
#define	SCECL81			82
#define	SCECL82			83
#define	SCECL83			84
#define	SCECL84			85
#define	SCECL85			86
#define	SCECL86			87
#define	SCECL87			88
#define	SCECL88			89
#define	SCECL89			90
#define	SCECL90			91
#define	SCECL91			92
#define	SCECL92			93
#define	SCECL93			94
#define	SCECL94			95
#define	SCECL95			96
#define	SCECL96			97
#define	SCECL97			98
#define	SCECL98			99
#define	SCECL99			100

#define	B_SCECL0		1001
#define	B_SCECL1		1002
#define	B_SCECL2		1003
#define	B_SCECL3		1004
#define	B_SCECL4		1005
#define	B_SCECL5		1006
#define	B_SCECL6		1007
#define	B_SCECL7		1008
#define	B_SCECL8		1009
#define	B_SCECL9		1010
#define	B_SCECL10		1011
#define	B_SCECL11		1012
#define	B_SCECL12		1013
#define	B_SCECL13		1014
#define	B_SCECL14		1015
#define	B_SCECL15		1016
#define	B_SCECL16		1017
#define	B_SCECL17		1018
#define	B_SCECL18		1019
#define	B_SCECL19		1020
#define	B_SCECL20		1021
#define	B_SCECL21		1022
#define	B_SCECL22		1023
#define	B_SCECL23		1024
#define	B_SCECL24		1025
#define	B_SCECL25		1026
#define	B_SCECL26		1027
#define	B_SCECL27		1028
#define	B_SCECL28		1029
#define	B_SCECL29		1030
#define	B_SCECL30		1031
#define	B_SCECL31		1032
#define	B_SCECL32		1033
#define	B_SCECL33		1034
#define	B_SCECL34		1035
#define	B_SCECL35		1036
#define	B_SCECL36		1037
#define	B_SCECL37		1038
#define	B_SCECL38		1039
#define	B_SCECL39		1040
#define	B_SCECL40		1041
#define	B_SCECL41		1042
#define	B_SCECL42		1043
#define	B_SCECL43		1044
#define	B_SCECL44		1045
#define	B_SCECL45		1046
#define	B_SCECL46		1047
#define	B_SCECL47		1048
#define	B_SCECL48		1049
#define	B_SCECL49		1050
#define	B_SCECL50		1051
#define	B_SCECL51		1052
#define	B_SCECL52		1053
#define	B_SCECL53		1054
#define	B_SCECL54		1055
#define	B_SCECL55		1056
#define	B_SCECL56		1057
#define	B_SCECL57		1058
#define	B_SCECL58		1059
#define	B_SCECL59		1060
#define	B_SCECL60		1061
#define	B_SCECL61		1062
#define	B_SCECL62		1063
#define	B_SCECL63		1064
#define	B_SCECL64		1065
#define	B_SCECL65		1066
#define	B_SCECL66		1067
#define	B_SCECL67		1068
#define	B_SCECL68		1069
#define	B_SCECL69		1070
#define	B_SCECL70		1071
#define	B_SCECL71		1072
#define	B_SCECL72		1073
#define	B_SCECL73		1074
#define	B_SCECL74		1075
#define	B_SCECL75		1076
#define	B_SCECL76		1077
#define	B_SCECL77		1078
#define	B_SCECL78		1079
#define	B_SCECL79		1080
#define	B_SCECL80		1081
#define	B_SCECL81		1082
#define	B_SCECL82		1083
#define	B_SCECL83		1084
#define	B_SCECL84		1085
#define	B_SCECL85		1086
#define	B_SCECL86		1087
#define	B_SCECL87		1088
#define	B_SCECL88		1089
#define	B_SCECL89		1090
#define	B_SCECL90		1091
#define	B_SCECL91		1092
#define	B_SCECL92		1093
#define	B_SCECL93		1094
#define	B_SCECL94		1095
#define	B_SCECL95		1096
#define	B_SCECL96		1097
#define	B_SCECL97		1098
#define	B_SCECL98		1099
#define	B_SCECL99		1100
#define	B_SCECL100		1101
#define	B_SCECL101		1102
#define	B_SCECL102		1103
#define	B_SCECL103		1104
#define	B_SCECL104		1105
#define	B_SCECL105		1106
#define	B_SCECL106		1107
#define	B_SCECL107		1108
#define	B_SCECL108		1109

/*
 * macros & defines for for FE-I4 raw data and trigger data processing
 */

/*
 * unformatted records
 */

// Data Header (DH)
#define DATA_HEADER						0x00E90000
#define DATA_HEADER_MASK				0xFFFF0000
#define DATA_HEADER_FLAG_MASK			0x00008000
#define DATA_HEADER_LV1ID_MASK			0x00007F00
#define DATA_HEADER_LV1ID_MASK_FEI4B	0x00007C00	// data format changed in fE-I4B. Upper LV1IDs comming in seperate SR.
#define DATA_HEADER_BCID_MASK			0x000000FF
#define DATA_HEADER_BCID_MASK_FEI4B		0x000003FF  // data format changed in FE-I4B due to increased counter size, See DATA_HEADER_LV1ID_MASK_FEI4B also.

#define DATA_HEADER_MACRO(X)			((DATA_HEADER_MASK & X) == DATA_HEADER ? true : false)
#define DATA_HEADER_FLAG_MACRO(X)		((DATA_HEADER_FLAG_MASK & X) >> 15)
#define DATA_HEADER_FLAG_SET_MACRO(X)	((DATA_HEADER_FLAG_MASK & X) == DATA_HEADER_FLAG_MASK ? true : false)
#define DATA_HEADER_LV1ID_MACRO(X)		((DATA_HEADER_LV1ID_MASK & X) >> 8)
#define DATA_HEADER_LV1ID_MACRO_FEI4B(X)		((DATA_HEADER_LV1ID_MASK_FEI4B & X) >> 10) // data format changed in fE-I4B. Upper LV1IDs comming in seperate SR.
#define DATA_HEADER_BCID_MACRO(X)		(DATA_HEADER_BCID_MASK & X)
#define DATA_HEADER_BCID_MACRO_FEI4B(X)		(DATA_HEADER_BCID_MASK_FEI4B & X) // data format changed in FE-I4B due to increased counter size, See DATA_HEADER_LV1ID_MASK_FEI4B also.

// Data Record (DR)
#define DATA_RECORD_COLUMN_MASK			0x00FE0000
#define DATA_RECORD_ROW_MASK			0x0001FF00
#define DATA_RECORD_TOT1_MASK			0x000000F0
#define DATA_RECORD_TOT2_MASK			0x0000000F

#define RAW_DATA_MIN_COLUMN				0x00000001 // 1
#define RAW_DATA_MAX_COLUMN				0x00000050 // 80
#define RAW_DATA_MIN_ROW				0x00000001 // 1
#define RAW_DATA_MAX_ROW				0x00000150 // 336
#define DATA_RECORD_MIN_COLUMN			(RAW_DATA_MIN_COLUMN << 17)
#define DATA_RECORD_MAX_COLUMN			(RAW_DATA_MAX_COLUMN << 17)
#define DATA_RECORD_MIN_ROW				(RAW_DATA_MIN_ROW << 8)
#define DATA_RECORD_MAX_ROW				(RAW_DATA_MAX_ROW << 8)

#define DATA_RECORD_MACRO(X)			(((DATA_RECORD_COLUMN_MASK & X) <= DATA_RECORD_MAX_COLUMN) && ((DATA_RECORD_COLUMN_MASK & X) >= DATA_RECORD_MIN_COLUMN) && ((DATA_RECORD_ROW_MASK & X) <= DATA_RECORD_MAX_ROW) && ((DATA_RECORD_ROW_MASK & X) >= DATA_RECORD_MIN_ROW) ? true : false)
#define DATA_RECORD_COLUMN1_MACRO(X)	((DATA_RECORD_COLUMN_MASK & X) >> 17)
#define DATA_RECORD_ROW1_MACRO(X)		((DATA_RECORD_ROW_MASK & X) >> 8)
#define DATA_RECORD_TOT1_MACRO(X)		((DATA_RECORD_TOT1_MASK & X) >> 4)
#define DATA_RECORD_COLUMN2_MACRO(X)	((DATA_RECORD_COLUMN_MASK & X) >> 17)
#define DATA_RECORD_ROW2_MACRO(X)		(((DATA_RECORD_ROW_MASK & X) >> 8) + 1)
#define DATA_RECORD_TOT2_MACRO(X)		(DATA_RECORD_TOT2_MASK & X)

// Address Record (AR)
#define ADDRESS_RECORD					0x00EA0000
#define ADDRESS_RECORD_MASK				0xFFFF0000
#define ADDRESS_RECORD_TYPE_MASK		0x00008000
#define ADDRESS_RECORD_ADDRESS_MASK		0x00007FFF

#define ADDRESS_RECORD_MACRO(X)			((ADDRESS_RECORD_MASK & X) == ADDRESS_RECORD ? true : false)
#define ADDRESS_RECORD_TYPE_MACRO(X)	((ADDRESS_RECORD_TYPE_MASK & X) >> 15)
#define ADDRESS_RECORD_TYPE_SET_MACRO(X)((ADDRESS_RECORD_TYPE_MASK & X) == ADDRESS_RECORD_TYPE_MASK ? true : false)
#define ADDRESS_RECORD_ADDRESS_MACRO(X)	(ADDRESS_RECORD_ADDRESS_MASK & X)

// Value Record (VR)
#define VALUE_RECORD					0x00EC0000
#define VALUE_RECORD_MASK				0xFFFF0000
#define VALUE_RECORD_VALUE_MASK			0x0000FFFF

#define VALUE_RECORD_MACRO(X)			((VALUE_RECORD_MASK & X) == VALUE_RECORD ? true : false)
#define VALUE_RECORD_VALUE_MACRO(X)		(VALUE_RECORD_VALUE_MASK & X)

// Service Record (SR)
#define SERVICE_RECORD					0x00EF0000
#define SERVICE_RECORD_MASK				0xFFFF0000
#define SERVICE_RECORD_CODE_MASK		0x0000FC00
#define SERVICE_RECORD_COUNTER_MASK		0x000003FF

#define SERVICE_RECORD_MACRO(X)			((SERVICE_RECORD_MASK & X) == SERVICE_RECORD ? true : false)
#define SERVICE_RECORD_CODE_MACRO(X)	((SERVICE_RECORD_CODE_MASK & X) >> 10)
#define SERVICE_RECORD_COUNTER_MACRO(X)	(SERVICE_RECORD_COUNTER_MASK & X)

#define SERVICE_RECORD_LV1ID_MASK_FEI4B	0x000003F8	// data format changed in fE-I4B. Upper LV1IDs comming in seperate SR.
#define SERVICE_RECORD_BCID_MASK_FEI4B	0x00000007  // data format changed in FE-I4B due to increased counter size, See DATA_HEADER_LV1ID_MASK_FEI4B also.

#define SERVICE_RECORD_LV1ID_MACRO_FEI4B(X)	((SERVICE_RECORD_LV1ID_MASK_FEI4B & X) >> 3) // data format changed in fE-I4B. Upper LV1IDs comming in seperate SR.
#define SERVICE_RECORD_BCID_MACRO_FEI4B(X)	(SERVICE_RECORD_BCID_MASK_FEI4B & X) // data format changed in FE-I4B due to increased counter size, See DATA_HEADER_LV1ID_MASK_FEI4B also.

// Empty Record (ER)
#define EMPTY_RECORD					0x00000000 // dummy, get value from ConfigFEMemory
#define EMPTY_RECORD_MASK				0xFFFFFFFF

#define EMPTY_RECORD_MACRO(X)			((EMPTY_RECORD_MASK & X) == EMPTY_RECORD ? true : false)

/*
 * trigger data
 */

#define TRIGGER_WORD_HEADER_V10			0x00FFFF00
#define TRIGGER_WORD_HEADER_MASK_V10	0xFFFFFF00

#define TRIGGER_WORD_HEADER				0x00F80000 // tolerant to 1-bit flips and not equal to control/comma symbols
#define TRIGGER_WORD_HEADER_MASK		0xFFFF0000
#define TRIGGER_NUMBER_31_24_MASK		0x000000FF
#define TRIGGER_NUMBER_23_0_MASK		0x00FFFFFF
#define TRIGGER_DATA_MASK				0x0000FF00 // trigger error + trigger mode
#define TRIGGER_MODE_MASK				0x0000E000 // trigger mode
#define TRIGGER_ERROR_MASK				0x00001F00 // error code: bit 0: wrong number of dh, bit 1 service record recieved

#define TRIGGER_WORD_MACRO(X)			((((TRIGGER_WORD_HEADER_MASK & X) == TRIGGER_WORD_HEADER) || ((TRIGGER_WORD_HEADER_MASK_V10 & X) == TRIGGER_WORD_HEADER_V10))? true : false)
//#define TRIGGER_NUMBER_MACRO(X)		(((TRIGGER_NUMBER_31_24_MASK & X) << 24) | (TRIGGER_NUMBER_23_0_MASK & (*((&X) + 4)))) // returns full trigger number; reference and dereference of following array element
#define TRIGGER_NUMBER_MACRO2(X, Y)		(((TRIGGER_NUMBER_31_24_MASK & X) << 24) | (TRIGGER_NUMBER_23_0_MASK & Y)) // returns full trigger number; reference and dereference of following array element
#define TRIGGER_ERROR_OCCURRED_MACRO(X)	((((TRIGGER_ERROR_MASK & X) == 0x00000000) || ((TRIGGER_WORD_HEADER_MASK_V10 & X) == TRIGGER_WORD_HEADER_V10)) ? false : true)
#define TRIGGER_DATA_MACRO(X)			((TRIGGER_DATA_MASK & X) >> 8)
#define TRIGGER_ERROR_MACRO(X)			((TRIGGER_ERROR_MASK & X) >> 8)
#define TRIGGER_MODE_MACRO(X)			((TRIGGER_MODE_MASK & X) >> 13)

#endif // DEFINES_H
