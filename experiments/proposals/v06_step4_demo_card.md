# Biography of agent:0

Run seed 7 | ruleset 0.6.0 | rng blake2b-v1

- lived ticks 0..99 (died)
- journal: 11084 committed / 187 rejected (every «no» of the world is recorded)
- card fingerprint: `73b599e6118149e5`

## Death

- T51 `disease.infect` (ImmuneDiseaseSystem, tid 6837)
- the die: roll 0.0029 < p 0.0256 — disease.infection
- wrote agent:0.infected: False -> True
- wrote agent:0.immune_memory: 0.7 -> 1.0
- wrote agent:0.health: 1.7099239300248605 -> 0.0
- wrote agent:0.alive: True -> False

## Necessary causes (backward trace, depth<=24, TRUNCATED)

-             T1 law: `agent.health` (AgentSystem) @depth 19
-             T2 law: `agent.health` (AgentSystem) @depth 18
-             T3 law: `agent.health` (AgentSystem) @depth 17
-             T4 law: `agent.health` (AgentSystem) @depth 16
-             T5 law: `agent.health` (AgentSystem) @depth 15
-             T6 law: `agent.health` (AgentSystem) @depth 14
-             T7 choice: `player.act` (PlayerAgentSystem) @depth 13
-             T0 choice: `player.act` (PlayerAgentSystem) @depth 12
-             T8 choice: `player.act` (PlayerAgentSystem) @depth 12
-             T1 law: `agent.metabolism` (AgentSystem) @depth 11
-             T1 choice: `player.act` (PlayerAgentSystem) @depth 11
-             T9 law: `agent.health` (AgentSystem) @depth 11
-             T9 choice: `player.act` (PlayerAgentSystem) @depth 11
-             T35 law: `agent.health` (AgentSystem) @depth 11
-             T2 law: `agent.metabolism` (AgentSystem) @depth 10
-             T2 choice: `player.act` (PlayerAgentSystem) @depth 10
-             T10 choice: `player.act` (PlayerAgentSystem) @depth 10
-             T27 law: `agent.health` (AgentSystem) @depth 10
-             T36 law: `agent.health` (AgentSystem) @depth 10
-             T3 law: `agent.metabolism` (AgentSystem) @depth 9
-             T3 choice: `player.act` (PlayerAgentSystem) @depth 9
-             T5 law: `agent.metabolism` (AgentSystem) @depth 9
-             T8 law: `agents.census` (AgentSystem) @depth 9
-             T11 choice: `player.act` (PlayerAgentSystem) @depth 9
-             T13 law: `agent.health` (AgentSystem) @depth 9
-             T28 law: `agent.health` (AgentSystem) @depth 9
-             T28 choice: `player.act` (PlayerAgentSystem) @depth 9
-             T37 law: `agent.health` (AgentSystem) @depth 9
-             T0 law: `agents.census` (AgentSystem) @depth 8
-             T4 choice: `player.act` (PlayerAgentSystem) @depth 8
- … 177 more causes in the card data (presentation cap only — the trace stays complete)

## Conditions (what fed him, what wore him down)

**health**
- `player.act` (PlayerAgentSystem): 18 writes, Δ -90.00 (+0/−18), mean -5.000
- `agent.health` (AgentSystem): 31 writes, Δ +34.50 (+28/−3), mean +1.113
- `disease.infect` (ImmuneDiseaseSystem): 3 writes, Δ -14.53 (+0/−3), mean -4.842
**hunger**
- `player.act` (PlayerAgentSystem): 32 writes, Δ -0.60 (+14/−10), mean -0.019
- `agent.metabolism` (AgentSystem): 20 writes, Δ +0.39 (+7/−6), mean +0.020

## Decisions (one node per action; idle counted too)

- **work** (T0)
- **explore** ×3 (T1..T3)
- **idle** (T4)
- **migrate** ×2 (T5..T6)
- **work** ×2 (T7..T8)
- **idle** (T9)
- **work** ×3 (T10..T12)
- **explore** (T13)
- **idle** (T14)
- **migrate** ×2 (T15..T16)
- **work** (T17)
- **explore** (T18)
- **work** (T19)
- **idle** (T20)
- **migrate** (T21)
- **idle** (T22)
- **work** (T23)
- **idle** (T24)
- **work** ×2 (T25..T26)
- **migrate** (T27)
- **explore** ×2 (T28..T29)
- **idle** (T30)
- **work** ×2 (T31..T32)
- **idle** (T33)
- **work** (T34)
- **idle** (T35)
- **migrate** (T36)
- **explore** (T37)
- **idle** (T38)
- **explore** (T39)
- **idle** (T40)
- **work** (T41)
- **idle** ×2 (T42..T43)
- **work** (T44)
- **explore** ×2 (T45..T46)
- **work** (T47)
- **idle** (T48)
- **explore** (T49)
- **work** (T50)
- **explore** (T51)

## Legacy

- no recorded descendants
- left the ruins standing

