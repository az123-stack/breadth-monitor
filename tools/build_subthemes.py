"""One-off helper: writes data/subthemes.csv (group, subtheme, ticker).

Sub-themes are peer groups by what the company actually sells, so names that
move on the same news sit together even when they live in different themes.
Every stock has exactly one sub-theme. After this, edit data/subthemes.csv.
Format below:  GROUP | Sub-theme | tickers
"""
import csv
from pathlib import Path

SUB = """
AI Infrastructure | AI Accelerators & GPUs | NVDA AMD
AI Infrastructure | Custom Silicon & Networking Chips | AVGO MRVL ALAB CRDO ARM
AI Infrastructure | AI Servers & Integrators | SMCI CLS JBL FLEX WYFI
AI Infrastructure | Enterprise AI Infrastructure (Servers, Storage, HCI) | DELL HPE NTNX PSTG NTAP
AI Infrastructure | Memory & Storage Media | MU SNDK WDC STX
AI Infrastructure | Data Center Networking | ANET CSCO CIEN NOK
AI Infrastructure | Optical Components & Transceivers | LITE COHR AAOI FN POET IPGP MTSI
AI Infrastructure | Neoclouds & GPU Hosting | CRWV NBIS IREN APLD CORZ WULF CIFR GLXY
AI Infrastructure | Data Center REITs | EQIX DLR IRM
Semiconductors | Semicap Equipment | ASML AMAT LRCX KLAC TER FORM
Semiconductors | Foundry | TSM INTC
Semiconductors | Analog & Power Semis | ADI TXN ON NXPI MPWR
Semiconductors | Mobile & Edge Chips | QCOM
Software | Hyperscalers | MSFT AMZN GOOGL ORCL META
Software | AI Applications & Platforms | PLTR AI SOUN BBAI APP PATH
Software | Enterprise SaaS | CRM NOW WDAY ADBE INTU TEAM HUBS SAP BILL
Software | Data & Observability | SNOW MDB DDOG ESTC CFLT DOCN IBM
Software | Design & Engineering Software | CDNS SNPS ADSK
Software | Cybersecurity Platforms | CRWD PANW FTNT ZS NET CHKP
Software | Identity & Security Tools | OKTA S CYBR QLYS TENB RPD VRNS
Internet & Consumer Tech | E-Commerce Marketplaces | SHOP MELI ETSY EBAY W CHWY CPNG REAL PRTS BYON GLBE CART JMIA
Internet & Consumer Tech | China Internet | BABA PDD JD BIDU NTES BILI IQ TME BEKE TCOM FUTU YUMC ZTO
Internet & Consumer Tech | Social & Ad Platforms | SNAP PINS RDDT MTCH BMBL YELP ZG DJT NXDR TTD
Internet & Consumer Tech | Streaming & Media | NFLX SPOT ROKU
Internet & Consumer Tech | Gaming Publishers & Platforms | TTWO EA RBLX U SONY PLTK SCPL GRVY
Internet & Consumer Tech | Travel & Gig Platforms | ABNB UBER DASH BKNG MMYT YTRA GRAB SE
Internet & Consumer Tech | Consumer Apps | DUOL HIMS
Fintech & Crypto | Payments & Networks | V MA PYPL XYZ TOST
Fintech & Crypto | Digital Banks & Lenders | SOFI NU AFRM UPST
Fintech & Crypto | Crypto Exchanges & Brokers | COIN HOOD CRCL CME
Fintech & Crypto | Bitcoin Treasury Companies | MSTR
Fintech & Crypto | Ethereum Treasury Companies | BMNR SBET BTCS
Fintech & Crypto | Bitcoin Miners | MARA RIOT CLSK HUT BITF HIVE BTDR BTBT
Robotics & Autonomy | Robotaxi & Self-Driving | TSLA MBLY AUR PONY WRD
Robotics & Autonomy | Lidar & Vision | LAZR OUST HSAI INVZ CGNX
Robotics & Autonomy | Industrial & Surgical Robots | ISRG ROK SYM SERV PRCT RR KSCP ZBRA NDSN
Robotics & Autonomy | EV Makers | RIVN LCID NIO XPEV LI
Robotics & Autonomy | Auto Tech Suppliers | APTV
Consumer | Display & Electronics (Korea) | LPL
Quantum | Quantum Computing | IONQ RGTI QBTS QUBT ARQQ LAES QMCO
Aerospace & Defense | Defense Primes | LMT NOC GD RTX LHX HII
Aerospace & Defense | Defense IT & Services | BAH CACI SAIC LDOS PSN
Aerospace & Defense | Defense Tech & Electronics | AXON KTOS MRCY DRS CW
Aerospace & Defense | Commercial Aerospace | BA GE HWM TDG HEI TXT ERJ
Aerospace & Defense | Military Drones & Counter-UAS | AVAV RCAT UMAC ONDS DPRO AIRO PDYN
Aerospace & Defense | eVTOL & Air Taxis | JOBY ACHR EH
Space | Launch & Space Systems | RKLB FLY RDW KRMN SPCE LUNR
Space | Satellite Connectivity & Imaging | ASTS IRDM GSAT SATS PL BKSY
Power & Grid | Nuclear Reactors (SMR) | OKLO SMR NNE
Power & Grid | Nuclear Fuel & Enrichment | LEU BWXT
Power & Grid | Independent Power Producers | CEG VST TLN NRG
Power & Grid | Gas Turbines & Grid Equipment | GEV ETN HUBB POWL AMSC PLPC AYI ESE ITRI
Power & Grid | Data Center Power & Cooling | VRT NVT MOD
Power & Grid | On-site Power & Fuel Cells | BE PLUG FCEL BLDP GNRC CMI CAT BW AROC
Power & Grid | Grid & Electrical Contractors | PWR MTZ EME PRIM MYRG IESC DY AGX FIX
Power & Grid | Regulated Utilities | NEE SO DUK AEP D EXC XEL SRE PCG ED ETR PEG
Clean Energy | Solar Manufacturers | FSLR CSIQ JKS DQ MAXN SOL
Clean Energy | Solar Inverters & Trackers | ENPH SEDG NXT ARRY SHLS TYGO ZEO TE
Clean Energy | Residential Solar & Yieldcos | RUN CWEN BEP BEPC AES HASI ORA
Clean Energy | Batteries & Storage | FLNC EOSE ENVX QS SLDP AMPX ESS MVST
Clean Energy | Lithium | ALB SQM LAC SGML LAR ATLX IONR
Clean Energy | Industrial Gases & Hydrogen | APD LIN CLNE
Energy | Integrated & Large-cap Oil | XOM CVX COP SHEL TTE BP PBR CVE SU YPF VIST
Energy | Shale E&P | EOG OXY DVN FANG APA
Energy | Natural Gas Producers | EQT AR RRC CNX EXE CTRA GPOR
Energy | LNG & Midstream | LNG CQP KMI WMB AM DTM NFE
Energy | Refiners | PSX MPC VLO
Energy | Oil Services & Drillers | SLB HAL BKR FTI NOV TS NE RIG WFRD VAL LBRT PTEN HP TDW
Energy | Uranium Miners | CCJ NXE UEC DNN UUUU URG EU
Metals & Mining | Gold Majors & Royalties | NEM AEM B WPM FNV RGLD OR KGC AU GFI HMY
Metals & Mining | Gold Mid-tiers | AGI EGO NGD IAG SBSW
Metals & Mining | Silver Miners | PAAS CDE HL AG EXK FSM SSRM SVM ASM USAS
Metals & Mining | Copper Miners | FCX SCCO TECK HBM ERO CMCL IE TGB
Metals & Mining | Diversified Miners | BHP RIO VALE NEXA
Metals & Mining | Aluminum | AA CENX
Metals & Mining | Rare Earths & Critical Minerals | MP USAR UAMY NB TMC
Metals & Mining | Steel | NUE STLD RS CLF CMC TX MT GGB PKX
Metals & Mining | Commodity ETFs | SLV CORN WEAT SOYB
Agriculture | Fertilizers & Crop Inputs | NTR CF MOS IPI FMC CTVA CMP
Agriculture | Farm Equipment & Ag Processing | DE AGCO CNH ADM BG LW
Biotech & Health | Large-cap Pharma | LLY NVO MRK PFE ABBV BMY AZN NVS SNY GSK JNJ AMGN GILD TAK TEVA VTRS RDY ZTS
Biotech & Health | Obesity & Metabolic | VKTX MDGL
Biotech & Health | Large-cap Biotech | VRTX REGN ALNY ARGX INSM NBIX INCY UTHR BMRN BNTX ONC
Biotech & Health | Mid-cap Biotech | EXEL RVMD IONS SRPT RARE MRNA LEGN CYTK KRYS AXSM PTCT
Biotech & Health | Gene Editing | CRSP NTLA BEAM EDIT
Biotech & Health | Genomics & Diagnostics | ILMN PACB TXG NTRA GH VCYT WGS QGEN TWST CDNA TEM
Biotech & Health | AI Drug Discovery & Synbio | RXRX ABSI SDGR DNA
Biotech & Health | Medical Devices | BSX SYK MDT ABT EW ZBH STE TFX PEN GMED NVST LIVN GEHC
Biotech & Health | Diabetes & Cardio Devices | DXCM PODD IRTC TMDX RMD
Biotech & Health | CROs | MEDP
Financials | Money-center Banks | JPM BAC WFC C
Financials | Investment Banks & Brokers | GS MS SCHW BK
Financials | Super-regional Banks | USB PNC TFC COF FITB MTB KEY RF CFG HBAN
Financials | Regional & Community Banks | WAL ZION CMA EWBC UMBF FFIN CATY BANR CVBF NBTB IBCP TOWN BANC
Financials | P&C Insurers | PGR TRV CB ALL HIG ACGL WRB L
Financials | Life Insurers | MET PRU AFL AIG
Financials | Global & EM Banks | HSBC SAN MUFG SMFG MFG HDB IBN KB SHG ITUB BBD BSBR GGAL BAP CIB IX NMR
Real Estate & Housing | Homebuilders | DHI PHM NVR LEN TOL TMHC MHO KBH MTH SKY
Real Estate & Housing | Building Products | IBP TREX MAS FBIN AWI CSL BLDR
Real Estate & Housing | REITs | PLD PSA O WELL SPG AVB EQR VTR IIPR
Real Estate & Housing | Tower REITs | AMT CCI SBAC
Infrastructure | Engineering & Construction | ACM FLR STRL ROAD GVA
Infrastructure | Aggregates & Materials | VMC MLM
Infrastructure | Industrial Distribution & Rental | FAST URI
Infrastructure | Industrial Automation | EMR AME HON CARR
Infrastructure | Water Utilities | AWK WTRG CWT MSEX
Infrastructure | Water Technology | XYL PNR WMS ERII ZWS FELE VLTO
Consumer | Airlines | UAL DAL AAL LUV ALK JBLU ALGT SKYW ULCC SNCY RYAAY CPA
Consumer | Online Sports Betting | DKNG FLUT RSI SGHC
Consumer | Casinos & Gaming Equipment | MGM CZR PENN BALY ACEL GDEN LNW EVRI
Consumer | Restaurants | TXRH WING CAVA
Consumer | Consumer Brands | CELH ELF ANF DEO RACE UL ABEV
Consumer | Cannabis | TLRY CGC CRON SNDL ACB OGI GRWG
Consumer | Used Autos | CVNA
Consumer | Autos (Japan) | TM HMC
Telecom | Wireless Carriers | TMUS VZ T KEP
Telecom | Telecom Equipment & Test | ERIC KEYS VIAV
Industrials | Trucking & Logistics | SAIA
International | India IT Services | INFY WIT SIFY
"""


def main():
    out = Path(__file__).resolve().parent.parent / "data" / "subthemes.csv"
    rows, seen = [], {}
    for line in SUB.strip().splitlines():
        group, sub, tickers = [p.strip() for p in line.split("|")]
        for t in tickers.split():
            if t in seen:
                raise SystemExit(f"{t} is in both '{seen[t]}' and '{sub}'")
            seen[t] = sub
            rows.append({"group": group, "subtheme": sub, "ticker": t})
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["group", "subtheme", "ticker"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows, {len({r['subtheme'] for r in rows})} sub-themes -> {out}")


if __name__ == "__main__":
    main()
