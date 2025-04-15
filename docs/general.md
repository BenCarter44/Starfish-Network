
<img src="https://codingcando.com/blog/media/f83e22273905f19e882eab3667f6a7c9267ff135848b62c9450f4e7c1d2771c7.jpeg" style="width: 100%">

# Starfish OS

*Starfish OS:* A decentralized and distributed operating system!   
&copy; Benjamin Carter 2025. Code License: AGPLv3

## TL;DR (Just give me the links)
[Watch a video of a OS visual that demonstrates node communication in real time here.](https://codingcando.com/fileShare/file?code=CD2KBNHH23)

[See a demo of StarfishOS in action (no sound)](https://codingcando.com/fileShare/file?code=starfishUse)

[View my research poster here.](https://codingcando.com/fileShare/file?code=starfishOS)

[View the GitHub repository here.](https://github.com/BenCarter44/Starfish-Network/tree/main)

This project was presented in front of Grand Canyon University Administration, including the Provost and President of the University, in the GCU Undergraduate Research Symposium. [See the news article.](https://news.gcu.edu/gcu-news/students-highlight-unique-studies-at-research-symposium/)


## The Mission

A ultra-reliable global scale OS behaving as "one gigantic computer". Deploying an application is as easy as deploying to "localhost". An OS that will never turn off and an OS that increases security through anonymization and distributing user data (no more data silos).

Want in on the mission? Contact me at [my contact page](https://codingcando.com/#contact).

Imagine if several thousand cellphones/laptops/desktops could be connected together to behave as like one VM? What if there was an OS that natively handled all this distributed work transparently to the user, so all the user would see is the CLI of this "virtual machine" that resembles any other operating system?

## Overview
As far as my research has been, nothing quite like this today exists yet, an OS with the following design goals:
1. An OS that has the usual: tasks/processing, files, and I/O.
2. An OS that has no central controller, all nodes in the OS are equal in the eyes of the OS.
3. An OS that uses distributed algorithms in all areas (no central scheduler, processing, etc...)
4. An OS where each node can come and go at anytime, yet remain stable.
5. An OS that can effectively scale to millions of devices in a somewhat federated manner.

It basically brings together current designs of peer-to-peer filesystems and concepts of computer networking and ties them together from a OS perspective, focusing on tasks/processing as well as data storage. 

Because, what is an OS from a high level?
1. It schedules processes
2. It handles memory
3. It handles I/O
4. It has some sort of file system

So, if an OS could be made that features the above components in a distributed and decentralized manner, it would then be a distributed OS. That is what Starfish OS is.

> However, I did a twist. I have found that having a shared distributed memory is not necessary. So, I therefore made a *memoryless* system. This is to allow for scaling to large numbers of devices

## How to use the PoC

[View the GitHub Repository here.](https://github.com/BenCarter44/Starfish-Network/tree/main)

The StarfishOS is a OS that utilizes a pool of underlying devices, "nodes". So, the PoC has all the code for a node 
inside a Docker container to allow for multiple nodes to be simulated on one machine.

1. Start a swarm of docker containers built using the repository's Dockerfile.
2. Open a Telnet connection to one of the docker containers. This is "Kernel Mode", for interacting with the actual node and adjusting its behavior. This is not the StarfishOS shell yet. The telnet connection is accessible by the "io-port" of the docker container.
3. You likely will want to connect your node to another node. Use `peer connect -p PEERID -t TRANSPORTADDR` for that. You will want at least four peers connected. 
4. "Login" as a user by running a shell attach command: `shell attach -u USERNAME`. Note, the username must be a max of 6 characters.
5. Now, inside the shell, this is the StarfishOS. It supports a limited set of commands:
	1. `ls` and `ls -d` for listing files/devices
	2. `write -f FILENAME CONTENT` for writing CONTENT to file FILENAME
	3. `cat FILENAME` for displaying file content
	4. `run hello.star` run a program (use the names found in the `/examples` directory in the GitHub repo)
6. To go back to kernel mode, type `kernel`. To go back to shell from kernel, type `exit`
7. To end the shell, type `disconnect`. This stops the shell program and sends you back to the node's kernel interface.


> Note, the shell program is an actual process running on the StarfishOS! Uses I/O through the Starfish API. See the code for `shell.star` for an example on how to use the StarfishOS APIs.

> You will want at least four nodes at all times on. After experimentation, under four can lead to problems.

Here below is the StarfishOS shell:   
![StarfishOS shell preview](https://codingcando.com/blog/media/4e841d5c8792a458054e6a829c1b697d09a999e0286011202d7838731ef2f03b.webp)   
   

[See a demo of StarfishOS in action (no sound)](https://codingcando.com/fileShare/file?code=starfishUse)

If you want to effectively control a large amount of docker containers / nodes, use the simulation suite (see last section in this document) which acts as a remote Docker orchestrator across a large number of hosts.  

> Note, this is just a PoC, meaning that there are some serious security assumptions. Do not use in production.

### To write your own programs for execution on StarfishOS

All programs are written in the "Star" format, a functional programming approach to Python. Take a look at the `/docs/STAR_FRAMEWORK.md` file for more information. Then, you compile it and save it in the `/examples` directory and then the OS can run it! [See the Starfish repository.](https://github.com/BenCarter44/Starfish-Network)


## Architecture

![Architecture diagram](https://codingcando.com/blog/media/6f041e498d43dea9926b50c4dddf5ec060296fe25e6c2581693a985b022b8857.png)

### OS Architecture Backbone
- Distributed Hash Tables (DHTs) are the backbone
- Users disassociated from physical nodes
	-   Increases security
		- Anonymous and private computing
	-	Increases reliability
		- User not “locked down” to a physical node
	-	Renders physical nodes ephemeral
- Processes use syscalls to access kernel
- Nodes communicate using RPC messages
	- RPC DHT Update/Fetch
	- RPC Direct communication
- Node Sandbox (zero-trust node design)
	- Execution Engine
	- Raw file block storage
	- I/O Host

### Peer Management
- Nodes can directly connect to one another
- Nodes can discover one another thorugh the [Kademlia algorithm](https://pdos.csail.mit.edu/~petar/papers/maymounkov-kademlia-lncs.pdf)
- Nodes register keep-alive callbacks that trigger kernel events when a node leaves
- Nodes publish their transport address(es) on the Peer DHT


***Future peer management:***
To support a massive scale of quantity of devices, the PEER IDs will be set in such a way to allow for federation. A peer coming onto the network will first discover the peers around it geographically and then pick a PEER ID that is "near" them (in terms of hash distance). This then automatically favors requests to other close-by nodes which likely have a lower latency.

### Event-Based Processing

Long story short, it is largely a functional-based processing system.  

I redefined what a process and a task are:
- **A process** is a collection of tasks that can pass events to one another, akin to a "neural network" but with processing. It has an initial "start" event.
- **A task** is a stateless set of instructions that receive events and send events. State is carried in the event data. These tasks are stored across nodes in the OS.
- **An event** is a message that carries the state between tasks and contains routing information to find the next task
- **Dropout.** Events are journaled and replayed if node holding a task drops. Future will have auto-scaling.

**Implications**: This OS is ***memoryless!***  A large shared memory does not scale to 1000s of devices. Large states can be stored in the filesystem. Also, this OS ***natively supports parallelism!***

#### Future research into a specialized compiler
To take advantage of this, this would require a specialized compiler that can convert sequential code into this process/task/event architecture. Or, codebases can be refactored into this process/task architecture. The compiler is a subject of future research. 

### Distributed File System
- **Native:** to the user, it looks like any other OS, the file system is distributed transparently to the user
- **Storage:** Files are broken into blocks and stored across nodes with block addresses in the DHT. 
- **Dropout:** Events are journaled and replayed if node holding a task drops out.

#### Future work:
Add in auto-scaling, where files that are more frequently added will be replicated more.

### Distributed I/O

- **Native:** to the user, I/O devices are distributed transparently.
- **I/O:** A node receives a device connection, alerting the OS. The I/O device is addressed by the host node, so no dropout support is required.
- **I/O manager:** Sends/Receives OS RPC calls
- **Device Host:** Acts as the server for outside I/O connections
- **I/O device:** The external device connected.

#### Future work:
Add the equivalent of UNIX domain sockets, where multiple processes can communicate "internally" on StarfishOS.

## Proof-Of-Concept
I built a python proof-of-concept of the StarfishOS. It features the Star framework for defining processes and tasks (see the `/examples` directory in the [starfish repository](https://github.com/BenCarter44/Starfish-Network)). Then, the OS is written in Python as a proof-of-concept. (Don't use this in production)

### Python Proof-Of-Concept design
The Python Proof-Of Concept design splits some of the architecture into different files and classes. The items in `/src/communications` cover all the gRPC calls and servers. The gRPC protocol is defined under `/src/communications/protocol`. The items in `/src/core` correspond to the core classes that run the different components. The `star_engine.py` file acts as the execution engine for the processes. The `star_components.py` file contains the classes needed to support the Star framework for the end-user's programs. The other files give the File functions, DHT functions, and I/O functions.  

The utility directory `/src/util` contains utility code for different parts of the OS. 

The main `/src` directory contains the components that "tie-in" everything together. It also contains a script for a kernel mode to configure a running node.

The `/examples` directory contains all the star programs that follow the star format that run on StarfishOS. This includes a full-fledged shell program and a `hello-world` program that can be called from the shell.

### Simulation
There is a separate set of files that cover the simulation of the Starfish OS. The OS is not reliant on these simulation files in any way. As a node can be run in a docker container, the simulation scripts simply deploy these docker containers remotely through an MQTT message broker.

- `simulation_client.py` for running a docker orchestrator client on a host
- `simulation_manager.py` for running a "command server" that uses MQTT to communicate to the docker orchestrator clients
- `sim/server.py` for viewing logs via JS in browser
- `simulation_logger.py` captures logs from connected docker orchestrator hosts
- `simulation_test.py` used to run the simulation. Edit this to set up a simulation
- The other simulation files are for supporting the docker orchestrator
	- `sim-requirements.txt` Requirements specific to the docker orchestrator scripts
	- `src/util/sim_log.py` The only file integrated in the OS to relay the logging outside (via MQTT).
