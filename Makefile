# AXE2 make targets (all of them call the smart runner or the bootstrap; see README.md)
.PHONY: tools run failed plan cold list render studies all status route-test test why timing cache
tools:      ## install + self-test every tool (KiCad 9, libraries, ngspice, gmsh, ARM gcc, Java 25 + Freerouting, Python packages)
	scripts/bootstrap.sh
run:        ## run what is needed (failed, changed, missing, dependents)
	python3 run.py
failed:     ## re-run only the steps that failed last time
	python3 run.py --failed
plan:       ## show what would run and why
	python3 run.py --plan
cold:       ## everything, from scratch
	python3 run.py --cold
list:       ## steps, state, last result
	python3 run.py --list
render:     ## cut-away, exploded view, display plan
	python3 run.py --step render display-figure
studies:    ## the physics studies (slow)
	python3 run.py --with-studies
all:        ## required steps + renders + studies, as needed
	python3 run.py --with-render --with-studies
route-test: ## router self-test: rip nets on a routed board, reroute them with A*, DRC
	python3 tests/router_selftest.py
status:
	@cat STATUS.md
test:       ## self-test of the tools the checks rely on (result cache, SPICE converter, op-amp bench, runner): each test can fail
	python3 tests/selftest.py
timing:     ## time per step and the cache
	python3 run.py --timing
why:        ## explain one step: make why STEP=board:LR1
	python3 run.py --why $(STEP)
cache:      ## what the in-step result cache holds
	python3 src/simcache.py --stats
