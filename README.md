# Starfish-Network

A highly tolerant distributed network! Like a Starfish: No central brain, cut it in half, it stays alive! Rethinking distributed computing. Welcome to the Starfish-Network

Creating a "virtualized computer" that can run on hundreds of nodes, with the nodes constantly going in and out. This virtualized computer has highly tolerant storage, can execute processes, and also hosts a shared database. This also will be completely decentralized, as opposed to a common technique of having a "master" server. All nodes are "treated the same"

Imagine a table with one hundred table legs. Now, imagine those table legs randomly appearing and disappearing. Will the table stay standing? This network seeks to make this possible, make a sturdy execution/storage environment highly tolerant of individual nodes coming and leaving.

---

This is currently a research project for [Benjamin Carter's](https://codingcando.com/) undergraduate capstone under the direction of Professor [Isac Artzi](https://www.gcu.edu/faculty-list) in Grand Canyon University's Artificial Intelligence Research and Design Program (RDP).

---

## Overview

A simple lay-man definition of a computer is this: A machine that:
- Can execute stuff (Execution Environment)
- Can store stuff short term (Memory)
- Can store stuff long term (Persistent Storage)
- Has input and output. (IO)

So, the Starfish Network seeks to recreate the above, to "simulate a computer".

- A Distributed CPU-like platform
- A Distributed Memory
- A Distributed Persistent Storage (Virtual Disk/File System)
- A Distributed Approach to IO

It seeks to combine those into one unified system. A completely distributed OS.

The goal is to have a node runnable in a Docker container, which can be deployed 
almost anywhere. These nodes together will simulate one large computer, while being highly 
tolerant of node failure and without relying on a single node for coordination. All nodes
are equal.

**This system currently is a proof-of-concept as of now and is a prototype**

## Features and Development Outline

#### Current Features Implemented in Prototype

1. Underlying communications protocol
2. Simple Key-Value All-Node Broadcast Memory
3. Node-to-node synchronous data transfer (both peers must be awake at the same time).

#### Next-To-Be-Implemented Features

4. Distributed File System (uses a Distributed Hash Table System, will be similar to IPFS)
5. Node-to-node async. data transfer (likely will use the file system and other techniques)

#### Future Features

6. Distributed CPU Processing Engine with functional/async model
7. Security of all network traffic
8. Simple bash-like terminal to interact with the distributed computer.

#### Wishes for way out in the future
9. Port Docker Container to a WASM approach, running in-browser as a PoC of durability of network
10. ???
