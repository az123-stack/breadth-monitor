exec(open("iterate.py").read().split('print("split"')[0])
s15 = col(r10.rolling(15, min_periods=1).max() >= 1.5)
Q = (D["rsmed"] >= 70) | (D["near"] >= 0.25)
run = I / I.rolling(120).min() - 1
for n in (20, 40):
    print(f"\n--- {n} --- base {fwd[n].loc[warm:].stack().dropna().mean()*100:+.2f}%")
    st(IGN & Q, n, "IGN + leaders (RS med>=70 or 25% near hi)")
    st(IGN & ~Q, n, "IGN no leaders")
    st(IGN & (D['rsmed']>=70) & (D['near']>=0.25), n, "IGN + both")
    st(IGN & Q & s15, n, "IGN + leaders + gate15")
    st(IGN & ~Q & s15, n, "IGN no leaders + gate15")
    st(IGN & Q & ~s15, n, "IGN + leaders, no gate")
    st(IGN & Q & (run <= 0.4), n, "IGN + leaders + run<=40%")
    st(IGN & (D['rsmed']>=60), n, "rsmed>=60"); st(IGN & (D['rsmed']>=80), n, "rsmed>=80")
    st(IGN & (D['near']>=0.4), n, "near>=40%")
print("overlap: P(Q | run>40%)", float(Q.where(IGN & (run > .4)).stack().mean()), "P(Q | run<=40%)", float(Q.where(IGN & (run <= .4)).stack().mean()))
# Day-1 with leaders
