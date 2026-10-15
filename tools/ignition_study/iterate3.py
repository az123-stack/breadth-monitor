exec(open("iterate.py").read().split('print("split"')[0])
Q = (D["rsmed"] >= 70) | (D["near"] >= 0.25)
s0 = col(r10 >= 1.5); s15 = col(r10.rolling(15, min_periods=1).max() >= 1.5)
for n in (20, 40):
    print(f"--- {n}")
    st(IGN & Q & s0, n, "leaders + strong today"); st(IGN & Q & ~s0 & s15, n, "leaders + strong in last 15 only"); st(IGN & Q & ~s15, n, "leaders + not strong 15")
    st(IGN & ~Q & s0, n, "no leaders + strong today"); st(IGN & ~Q & ~s0, n, "no leaders + not strong today")
