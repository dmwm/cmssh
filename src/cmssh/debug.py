#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
#
# Copyright 2008 Cornell University, Ithaca, NY 14853. All rights reserved.
#
# Author:  Valentin Kuznetsov, 2008

class DebugManager:
  def __init__(self):
      self.level= 0

  def set(self, level):
      self.level=level
