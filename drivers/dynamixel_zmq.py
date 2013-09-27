#!/usr/bin/env python

""" 
  Dynamixel-ZMQ driver for PyPose
  Copyright (c) 2013 Alexander 'E-Razor' Krause  All right reserved.

  This program is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 2 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program; if not, write to the Free Software Foundation,
  Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""
"""dynamixel commands"""
DYNAMIXEL_RQ_PING					=0x01
DYNAMIXEL_RQ_READ_DATA		=0x02
DYNAMIXEL_RQ_WRITE_DATA		=0x03
DYNAMIXEL_RQ_REG_WRITE		=0x04
DYNAMIXEL_RQ_REG_ACTION		=0x05
DYNAMIXEL_RQ_RESET				=0x06
DYNAMIXEL_RQ_SYNC_WRITE		=0x83


import time
import sys
import msgpack
import zmq
from ax12 import *

class Driver:
    """ Class to open a serial port and control AX-12 servos 
    through dynamixel_zmq """
    _zmqctx=None
    _socket=None

    def __init__(self, uri="tcp://127.0.0.1:5000", interpolation=False, direct=False):
        """ This may throw errors up the line -- that's a good thing. """
        self._zmqctx = zmq.Context()
        self._socket = self._zmqctx.socket(zmq.REQ)
        self._socket.connect(uri)
        self.error = 0
        self.hasInterpolation = interpolation
        self.direct = direct

    def execute(self, index, ins, params):
        """ Send an instruction to a device. """
        print('execute',index, ins, params)
        self._socket.send(msgpack.packb([ins, index]+params))
        ret=msgpack.unpackb(self._socket.recv())
        return ret

    def setReg(self, index, regstart, values):
        """ Set the value of registers. Should be called as such:
        ax12.setReg(1,1,(0x01,0x05)) """ 
        print('setReg',index,regstart,values)
        self._socket.send(msgpack.packb([DYNAMIXEL_RQ_WRITE_DATA, index, regstart,len(values)]+values))
        ret=msgpack.unpackb(self._socket.recv())
        return self.error

    def getReg(self, index, regstart, rlength):
        """ Get the value of registers, should be called as such:
        ax12.getReg(1,1,1) """
        print('getReg',index,regstart,rlength)
        self._socket.send(msgpack.packb([DYNAMIXEL_RQ_READ_DATA, index,regstart, rlength]))
        ret=msgpack.unpackb(self._socket.recv())
        self.error=ret[0]
        return ret[1:]

    def syncWrite(self, regstart, vals):
        """ Set the value of registers. Should be called as such:
        ax12.syncWrite(reg, ((id1, val1, val2), (id2, val1, val2))) """ 
        print('syncWrite',regstart,vals)
        data=[]
        id_count=len(vals)
        reg_count=len(vals[0])
        for cluster in vals:
          data=data+cluster
        self._socket.send(msgpack.packb([DYNAMIXEL_RQ_SYNC_WRITE, regstart]+data))
        ret=msgpack.unpackb(self._socket.recv())
        self.error=ret[0]

    def close(self):
        self._socket.close()
        
