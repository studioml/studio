#!/usr/bin/env python

'''This is a simple runner that takes random actions'''
import os, sys
import numpy as np

from studio import fs_tracker
from osim.env import RunEnv

VERBOSE = False
VISUALIZE = False
DIFFICULTY = 0
TIMESTEPS = 99999

env = RunEnv(visualize=VISUALIZE)
observation = env.reset(difficulty = DIFFICULTY)

total_reward = 5.0
for i in range(TIMESTEPS):
  observation, reward, done, info = env.step(env.action_space.sample())
  total_reward += reward

  if VERBOSE:
    print "Observation: %s" % observation
    print "Reward: %s" % reward
    print "Done: %s" % done
    print "Info: %s" % info
  if done:
    break

print "All finished, total reward is: %s" % total_reward
try:
  # total_reward += np.abs(np.sum(np.load(fs_tracker.get_artifact('lr'))))
  total_reward += np.abs(np.sum(np.random.rand((10,))))
except:
  pass
print "Fitness: %s" % max(total_reward, 1e-12)
