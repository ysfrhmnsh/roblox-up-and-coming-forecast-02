# Roblox Up-and-Coming Forecast — v2

Entry for the make.fun bounty roblox-up-and-coming-forecast-01: a program
that forecasts Roblox's Up-and-Coming top 10 for the 72 hours after entries
close. Monte Carlo rank simulation (Python 3.13, stdlib only, offline,
deterministic): each game has a latent rank-value that mean-reverts toward
a target extrapolated from its recent rank velocity, with band-dependent
noise; new games spawn at the bottom of the chart and a fraction are
"risers" climbing exponentially toward a top-10 target. See BUILD_NOTES.md
for the method, the v2 changes, and the validation scores.
