*******************************************************
* Stage-1: d_interest_rate_on_deposit
*  - Deposit-weighted region shares (NE MA EC WC SA ES WS MT PC)
*  - FFR change: d_ffr
*******************************************************

clear all
set more off

*------------------------------------------------------
* 0. Install reghdfe if needed
*------------------------------------------------------
cap which reghdfe
if _rc {
    ssc install reghdfe, replace
    ssc install ftools,  replace
}

*------------------------------------------------------
* 1. Import data and build panel
*------------------------------------------------------
import delimited "$working/working_panel.csv", clear varnames(1) stringcols(_all)

* Convert all non-date variables from string to numeric when possible
ds date, not
local vars_nodate `r(varlist)'
capture destring `vars_nodate', replace ignore(",")

* Convert Date (string) to daily date; adjust "YMD" if your format differs
gen float date_d = daily(date, "YMD")
format date_d %td

* Quarterly date
gen qdate = qofd(date_d)
format qdate %tq

* Panel declaration (not required by reghdfe, but good practice)
* Ensure bankid is numeric (encode if still string)
capture confirm numeric variable bankid
if _rc {
    encode bankid, gen(bankid_num)
    drop bankid
    rename bankid_num bankid
}

* Recast all numeric variables (including dates and ids) to float
ds, has(type numeric)
recast float `r(varlist)'

xtset bankid qdate

* Keep 2022Q1–2023Q4 = hike + plateau window
keep if inrange(qdate, tq(2022q1), tq(2023q4))

*------------------------------------------------------
* 2. Policy–exposure interactions (instruments)
*------------------------------------------------------
* HHI already in correct sign
gen zS_dffr = sophistication_index_z * d_ffr
gen zR_dffr = branch_density_z      * d_ffr
gen zH_dffr = hhi_z                 * d_ffr

*------------------------------------------------------
* 3. Define analysis sample
*   (you can add more variables to the missing() list if needed)
*------------------------------------------------------
gen byte sample_stage1 = ///
    !missing(d_interest_rate_on_deposit, zS_dffr, zR_dffr, zH_dffr, d_ffr, ///
             ne, ma, ec, wc, sa, es, ws, mt, pc)

* Prepare results logging (capture only regression output below)
cap mkdir "$result"
capture log close stage1
log using "$result/stage1_results.log", text replace name(stage1)

*------------------------------------------------------
* 4. Stage-1 regression
*
* Bank FE: absorbed via absorb(bank_id)
* Quarter FE: i.qdate
* Deposit-weighted region×quarter controls:
*   c.<region_share>#i.qdate, with PC omitted to avoid perfect collinearity
*------------------------------------------------------
reghdfe d_interest_rate_on_deposit ///
        zS_dffr zR_dffr zH_dffr ///
        i.qdate ///
        c.ne#i.qdate c.ma#i.qdate c.ec#i.qdate c.wc#i.qdate ///
        c.sa#i.qdate c.es#i.qdate c.ws#i.qdate c.mt#i.qdate ///
        if sample_stage1 , ///
        absorb(bankid) ///
        cluster(bankid)

* Test joint significance of the three policy–exposure interactions
test zS_dffr zR_dffr zH_dffr

*------------------------------------------------------
* 5. Subsample regressions by size (large_bank)
*------------------------------------------------------
* Large banks (large_bank == 1)
reghdfe d_interest_rate_on_deposit ///
        zS_dffr zR_dffr zH_dffr ///
        i.qdate ///
        c.ne#i.qdate c.ma#i.qdate c.ec#i.qdate c.wc#i.qdate ///
        c.sa#i.qdate c.es#i.qdate c.ws#i.qdate c.mt#i.qdate ///
        if sample_stage1  & large_bank == 1 , ///
        absorb(bankid) ///
        cluster(bankid)
test zS_dffr zR_dffr zH_dffr

* Small banks (large_bank == 0)
reghdfe d_interest_rate_on_deposit ///
        zS_dffr zR_dffr zH_dffr ///
        i.qdate ///
        c.ne#i.qdate c.ma#i.qdate c.ec#i.qdate c.wc#i.qdate ///
        c.sa#i.qdate c.es#i.qdate c.ws#i.qdate c.mt#i.qdate ///
        if sample_stage1  & large_bank == 0, ///
        absorb(bankid) ///
        cluster(bankid)
test zS_dffr zR_dffr zH_dffr

*------------------------------------------------------
* 4. Stage-1 regression
*
* Bank FE: absorbed via absorb(bank_id)
* Quarter FE: i.qdate
* Deposit-weighted region×quarter controls:
*   c.<region_share>#i.qdate, with PC omitted to avoid perfect collinearity
*------------------------------------------------------
reghdfe d_average_interest_bearing_depos ///
        zS_dffr zR_dffr zH_dffr ///
        i.qdate ///
        c.ne#i.qdate c.ma#i.qdate c.ec#i.qdate c.wc#i.qdate ///
        c.sa#i.qdate c.es#i.qdate c.ws#i.qdate c.mt#i.qdate ///
        if sample_stage1, ///
        absorb(bankid) ///
        cluster(bankid)

* Test joint significance of the three policy–exposure interactions
test zS_dffr zR_dffr zH_dffr

*------------------------------------------------------
* 5. Subsample regressions by size (large_bank)
*------------------------------------------------------
* Large banks (large_bank == 1)
reghdfe d_average_interest_bearing_depos ///
        zS_dffr zR_dffr zH_dffr ///
        i.qdate ///
        c.ne#i.qdate c.ma#i.qdate c.ec#i.qdate c.wc#i.qdate ///
        c.sa#i.qdate c.es#i.qdate c.ws#i.qdate c.mt#i.qdate ///
        if sample_stage1 & large_bank == 1 , ///
        absorb(bankid) ///
        cluster(bankid)
test zS_dffr zR_dffr zH_dffr

* Small banks (large_bank == 0)
reghdfe d_average_interest_bearing_depos ///
        zS_dffr zR_dffr zH_dffr ///
        i.qdate ///
        c.ne#i.qdate c.ma#i.qdate c.ec#i.qdate c.wc#i.qdate ///
        c.sa#i.qdate c.es#i.qdate c.ws#i.qdate c.mt#i.qdate ///
        if sample_stage1 & large_bank == 0, ///
        absorb(bankid) ///
        cluster(bankid)
test zS_dffr zR_dffr zH_dffr

reghdfe d_average_deposit ///
        zS_dffr zR_dffr zH_dffr ///
        i.qdate ///
        c.ne#i.qdate c.ma#i.qdate c.ec#i.qdate c.wc#i.qdate ///
        c.sa#i.qdate c.es#i.qdate c.ws#i.qdate c.mt#i.qdate ///
        if sample_stage1, ///
        absorb(bankid) ///
        cluster(bankid)
test zS_dffr zR_dffr zH_dffr

reghdfe d_average_deposit ///
        zS_dffr zR_dffr zH_dffr ///
        i.qdate ///
        c.ne#i.qdate c.ma#i.qdate c.ec#i.qdate c.wc#i.qdate ///
        c.sa#i.qdate c.es#i.qdate c.ws#i.qdate c.mt#i.qdate ///
        if sample_stage1 & large_bank == 0, ///
        absorb(bankid) ///
        cluster(bankid)
test zS_dffr zR_dffr zH_dffr


reghdfe d_average_deposit ///
        zS_dffr zR_dffr zH_dffr ///
        i.qdate ///
        c.ne#i.qdate c.ma#i.qdate c.ec#i.qdate c.wc#i.qdate ///
        c.sa#i.qdate c.es#i.qdate c.ws#i.qdate c.mt#i.qdate ///
        if sample_stage1 & large_bank == 1, ///
        absorb(bankid) ///
        cluster(bankid)
test zS_dffr zR_dffr zH_dffr

reghdfe d_average_interest_bearing_depos ///
        zS_dffr zR_dffr zH_dffr ///
        i.qdate ///
        c.ne#i.qdate c.ma#i.qdate c.ec#i.qdate c.wc#i.qdate ///
        c.sa#i.qdate c.es#i.qdate c.ws#i.qdate c.mt#i.qdate ///
        if sample_stage1, ///
        absorb(bankid) ///
        cluster(bankid)
test zS_dffr zR_dffr zH_dffr

reghdfe d_average_interest_bearing_depos ///
        zS_dffr zR_dffr zH_dffr ///
        i.qdate ///
        c.ne#i.qdate c.ma#i.qdate c.ec#i.qdate c.wc#i.qdate ///
        c.sa#i.qdate c.es#i.qdate c.ws#i.qdate c.mt#i.qdate ///
        if sample_stage1 & large_bank == 0, ///
        absorb(bankid) ///
        cluster(bankid)
test zS_dffr zR_dffr zH_dffr


reghdfe d_average_interest_bearing_depos ///
        zS_dffr zR_dffr zH_dffr ///
        i.qdate ///
        c.ne#i.qdate c.ma#i.qdate c.ec#i.qdate c.wc#i.qdate ///
        c.sa#i.qdate c.es#i.qdate c.ws#i.qdate c.mt#i.qdate ///
        if sample_stage1 & large_bank == 1, ///
        absorb(bankid) ///
        cluster(bankid)
test zS_dffr zR_dffr zH_dffr

* Close results log
log close stage1
