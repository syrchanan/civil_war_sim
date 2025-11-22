# Load Packages and Import Functions ----
if (!require("pacman")) {
  install.packages("pacman")
}
pacman::p_load(
  "tidyverse"
)
set.seed(8675309)

walk(list.files("./archive/functions/", pattern = ".R", full.names = T), source)

# Unit Stat Blocks ----

# unused at the moment, but want to eventually have a global admin scalar
casualty_scalar <- 0.2

coefs <- get_combat_efficiency(return_table = T)

# Set Unit Metadata ----

#  xp / morale / weapon / melee bool (0 = ranged)

init <- list(
  USA = list(
    size = 4000, # starting size
    stats = "4/4/0/0", # parsed for coef
    type = "sq" # law selection
  ),
  CSA = list(
    size = 3500, # starting size
    stats = "4/6/1/0", # parsed for coef
    type = "sq" # law selection
  )
)

# Simulation ----

## Set Up Simulation ----

sim <- build_lanchester_diffeq(
  init = map_vec(init, ~ .x$size),
  type = map_vec(init, ~ .x$type),
  stat = map_vec(init, ~ .x$stats)
)

## Run Simulation With Stochastic Markov Chain ----

# TODO - tune casualty constants, should be ok for now but keep in mind
markovchain_diffeq_sim(
  init = sim$state,
  rate_func = sim$rate_func,
  stat = sim$stat,
  time = 1
) -> out

tail(out$df)
out$final_casualties

# Scratch ----

# for linked testing

init2 <- list(
  USA = list(
    size = 0, # starting size
    stats = "4/7/0/0", # parsed for coef
    type = "sq" # law selection
  ),
  CSA = list(
    size = 0, # starting size
    stats = "4/7/0/0", # parsed for coef
    type = "sq" # law selection
  )
)

sim2 <- build_lanchester_diffeq(
  init = map_vec(init2, ~ .x$size),
  coef = map_dbl(init2, ~ parse_stat_string(pluck(.x, "stats"))),
  type = map_vec(init2, ~ .x$type)
)

stages <- list(sim, sim2)
deltas <- c(1, 3)

linked_mc_diffeq_sim(stages, deltas) %>%
  View()
