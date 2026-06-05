# Brain simulation

*Source: [Wikipedia](https://en.wikipedia.org/wiki/Brain_simulation)*
*Collected: 2026-06-05 17:53:21*

In the field of computational neuroscience, brain simulation is the concept of creating a functioning computer model of a brain or part of a brain. Brain simulation projects intend to contribute to a complete understanding of the brain, and eventually also assist the process of treating and diagnosing brain diseases. Simulations utilize mathematical models of biological neurons, such as the Hodgkin-Huxley model, to simulate the behavior of neurons, or other cells within the brain.
Various simulations from around the world have been fully or partially released as open source software, such as C. elegans, and the Blue Brain Project Showcase. In 2013 the Human Brain Project, which has utilized techniques used by the Blue Brain Project and built upon them, created a Brain Simulation Platform (BSP), an internet-accessible collaborative platform designed for the simulation of brain models.
Brain simulations can be done at varying levels of detail, with more detail requiring significantly higher computation capabilities. Some simulations may only consider the behaviour of areas without modeling individual neurons. Other simulations model the behaviour of individual neurons, the strength of the connections between neurons and how these connections change. This requires having a map of the target organism neurons and their connections, called a connectome. Highly detailed simulations may precisely model the electrophysiology of each individual neuron, potentially even their metabolome and proteome, and the state of their protein complexes.


== Case studies ==
Over time, brain simulation research has focused on increasingly complex organisms, starting with primitive organisms like the nematode C. elegans and progressing towards simulations of human brains.


=== Roundworm ===

The connectivity of the neural circuit for touch sensitivity of the simple C. elegans nematode (roundworm) was mapped in 1985 and partly simulated in 1993. Since 2004, many software simulations of the complete neural and muscular system have been developed, including simulation of the worm's physical environment. Some of these models including source code have been made available for download. However, there is still a lack of understanding of how the neurons and the connections between them generate the surprisingly complex range of behaviors that are observed in the relatively simple organism. This contrast between the apparent simplicity of how the mapped neurons interact with their neighbours, and exceeding complexity of the overall brain function, is an example of an emergent property. This kind of emergent property is paralleled within artificial neural networks, the neurons of which are exceedingly simple compared to their often complex, abstract outputs. To quote a common saying, a group (in this case a brain) is stronger than the sum of its parts.


=== Drosophila ===

The brain of the fruit fly, Drosophila, has also been thoroughly studied. A simulated model of the fruit fly's brain offers a unique model of sibling neurons. Like the roundworm, this has been made available as open-source software.


=== Mouse and rat ===
In 2006, the Blue Brain Project, led by Henry Markram, made its first model of a neocortical column with simplified neurons. And in November 2007, it completed an initial model of the rat neocortical column. This marked the end of the first phase, delivering a data-driven process for creating, validating, and researching the neocortical column. The neocortical column is considered the smallest functional unit of the neocortex. The neocortex is the part of the brain thought to be responsible for higher-order functions like conscious thought, and contains 10,000 neurons in the rat brain (and 108 synapses).
An artificial neural network described as being "as big and as complex as half of a mouse brain" with 8 million of neurons and 6300 synapses per neuron was run on an IBM Blue Gene supercomputer by the University of Nevada's research team and IBM Almaden in 2007. Each second of simulated time took ten seconds of computer time. The researchers claimed to observe "biologically consistent" nerve impulses that flowed through the virtual cortex. However, the simulation lacked the structures seen in real mice brains, and they intend to improve the accuracy of the neuron and synapse models. IBM later in the same year increased the number of neurons to 16 million and 8000 synapses per neuron, 5 seconds of which was modelled in 265 s of real time. By 2009, the researchers were able to ramp up the numbers to 1.6 billion neurons and 9 trillion synapses, saturating entire 144 TB of supercomputer RAM.
In 2019, Idan Segev, one of the computational neuroscientists working on the Blue Brain Project, gave a talk titled: "Brain in the computer: what did I learn from simulating the brain." In his talk, he mentioned that the whole cortex for the mouse brain was complete and virtual EEG experiments would begin soon. He also mentioned that the model had become too heavy on the supercomputers they were using at the time, and that they were consequently exploring methods in which every neuron could be represented as a neural network (see citation for details).
In 2023, researchers from Duke University performed a particularly high-resolution scan of a mouse brain.


==== Blue Brain ====
Blue Brain is a project that was launched in May 2005 by IBM and the Swiss Federal Institute of Technology in Lausanne. The intention of the project was to create a computer simulation of a mammalian cortical column down to the molecular level. The project uses a supercomputer based on IBM's Blue Gene design to simulate the electrical behavior of neurons based upon their synaptic connectivity and ion permeability. The project seeks to eventually reveal insights into human cognition and various psychiatric disorders caused by malfunctioning neurons, such as autism, and to understand how pharmacological agents affect network behavior.


=== Human ===
Human brains contain 86 billion neurons, each with an approximate average of 10,000 connections. By one estimate, a very detailed full reconstruction of the human connectome would require a zettabyte (1021 bytes) of data storage.
A supercomputer having similar computing capability as the human brain 
was scheduled to go online in April 2024. Called "DeepSouth", it could perform 228 trillions of synaptic operations per second.


==== K computer ====
In late 2013, researchers in Japan and Germany used the K computer, then 4th fastest supercomputer, and the simulation software NEST to simulate 1% of the human brain. The simulation modeled a network consisting of 1.73 billion nerve cells connected by 10.4 trillion synapses. To realize this feat, the program recruited 82,944 processors of the K Computer. The process took 40 minutes, to complete the simulation of 1 second of neuronal network activity in real, biological, time.


==== Human Brain Project ====
The Human Brain Project (HBP) was a 10-year program of research funded by the European Union. It began in 2013 and employed around 500 scientists across Europe. It includes 6 platforms: 

Neuroinformatics (shared databases),
Brain Simulation
High-Performance Analytics and Computing
Medical informatics (patient database)
Neuromorphic computing (brain-inspired computing)
Neurorobotics (robotic simulations).
The Brain Simulation Platform (BSP) is a device for internet-accessible tools, which allows investigations that are not possible in the laboratory. They are applying Blue Brain techniques to other brain regions, such as the cerebellum, hippocampus, and the basal ganglia.


== Open source ==
Various models of the brain have been released as open-source software and are available on sites such as GitHub, including the C. elegans roundworm, the Drosophila fruit fly, and the human brain models Elysia and Spaun, which are based on the NENGO software architecture. The Blue Brain Project Showcase likewise illustrates how models and data from the Blue Brain Project can be converted to NeuroML and PyNN (Python neuronal network models).
The Brain Simulation Platform (BSP) is an internet-accessible open collaboration platform for brain simulation, created by the Human Brain Project.


== See also ==
Mind uploading
Artificial general intelligence
Trion (neural networks)


== References ==