
# Load Packages and Import Functions ----
if (!require("pacman")) install.packages("pacman")
pacman::p_load(
  "tidyverse"
)
set.seed(8675309)

walk(list.files("./functions/", pattern = ".R", full.names = T), source)

# Unit Stat Blocks ----

casualty_scalar <- 0.2

expand.grid(
  stat_morale = 1:10,
  stat_xp = 1:10,
  stat_weapon = -2:2,
  stat_melee = 0:1
) %>% 
  mutate(
    active_morale = 10*stat_morale,
    adj_morale = log(stat_morale),
    adj_xp = log(stat_xp),
    adj_weapon = ( 1 + (1.1^(stat_weapon) - 1.1^-2)/(1.1^2 - 1.1^-2) ),
    adj_coef = (adj_morale + adj_xp + adj_weapon) / 6,
    active_coef_ranged = (adj_coef - min(adj_coef)) / (max(adj_coef) - min(adj_coef)) * 0.8,
    active_coef_melee = active_coef_ranged/2
  ) %>% 
  select(-matches("adj")) %>%
  mutate(across(starts_with("active_coef"), ~ .x * casualty_scalar)) -> unit_stats

# Set Unit Metadata ----

# morale / XP / weapon / melee bool

init <- list(
  USA = list(
    size = 4500, # starting size
    stats = "4/7/2/0", # parsed for coef
    type = "sq" # law selection
  ), 
  CSA = list(
    size = 3700, # starting size
    stats = "2/7/1/0", # parsed for coef
    type = "sq" # law selection
  )
)

map_vec(
  init, 
  ~ pluck(.x, "stats") %>% 
    str_split(., "\\/") %>% 
    map(as.numeric)
) %>% 
  map(~ set_names(.x, c("stat_morale", "stat_xp", "stat_weapon", "stat_melee"))) %>% 
  map_dbl(
    ~ unit_stats$active_coef_ranged[
      unit_stats$stat_morale == .x[1] & 
      unit_stats$stat_xp == .x[2] &
      unit_stats$stat_weapon == .x[3] &
      unit_stats$stat_melee == .x[4]
    ]
  ) -> coef

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
  coef = coef,
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
    size = 4500, # starting size
    stats = "3/6/1/0", # parsed for coef
    type = "sq" # law selection
  ), 
  CSA = list(
    size = 3700, # starting size
    stats = "2/7/1/0", # parsed for coef
    type = "sq" # law selection
  )
)

sim2 <- build_lanchester_diffeq(
  init = map_vec(init2, ~ .x$size),
  coef = coef,
  type = map_vec(init2, ~ .x$type)
)

stages <- list(sim, sim2)
deltas <- c(1, 3)

linked_mc_diffeq_sim(stages, deltas)
