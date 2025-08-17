
# Load Packages and Import Functions ----
if (!require("pacman")) install.packages("pacman")
pacman::p_load(
  "tidyverse"
)
set.seed(8675309)

walk(list.files("./functions/", pattern = ".R", full.names = T), source)

# Unit Stat Blocks ----

casualty_scalar <- 0.2

coefs <- get_combat_efficiency(return_table = T)

# Set Unit Metadata ----

#  xp / morale / weapon / melee bool (0 = ranged)

init <- list(
  USA = list(
    size = 4500, # starting size
    stats = "4/7/0/0", # parsed for coef
    type = "sq" # law selection
  ), 
  CSA = list(
    size = 6000, # starting size
    stats = "4/4/0/0", # parsed for coef
    type = "sq" # law selection
  )
)

# Coefficient Definition:
# for each 1 soldier, they kill N of the other side
# N * init = deaths on other side
# coef better forces > coef of weaker forces
# Example:
#   N = 1, takes 1 man to kill 1 man
#   N = 1/100, takes 100 men to kill 1 man

# Simulation ----

## Set Up Simulation ----

sim <- build_lanchester_diffeq(
  init = map_vec(init, ~ .x$size),
  coef = map_dbl(init, ~  parse_stat_string(pluck(.x, "stats"))),
  type = map_vec(init, ~ .x$type)
)

## Run Simulation With Stochastic Markov Chain ----

markovchain_diffeq_sim(
  init = sim$state,
  rate_func = sim$rate_func, 
  time = 1
) -> df

tail(df)

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
  coef = map_dbl(init2, ~  parse_stat_string(pluck(.x, "stats"))),
  type = map_vec(init2, ~ .x$type)
)

stages <- list(sim, sim2)
deltas <- c(1, 3)

linked_mc_diffeq_sim(stages, deltas) %>% 
  View()
