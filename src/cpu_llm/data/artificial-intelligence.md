This primer is original text written for the cpu-llm index. It is an introduction to artificial intelligence, stored as paragraphs beside the WikiText articles. It is not a copy of another textbook.

Artificial intelligence is the study of methods that let a machine carry out a task associated with intelligent behavior. The tasks include perception, language, planning, and learning.

A task is a mapping from an observed input to an output. The output can be a label, a number, a sentence, or an action.

An agent is a system that selects an action from what it observes. The selection is the decision the agent makes at one moment.

An environment is the part of the world that an action can change. The agent receives a new observation after the action.

A percept is the information an agent receives from the environment. A camera image, a sentence, and a sensor reading are percepts.

A rational agent is an agent that selects an action expected to reach its goal. The goal is supplied by the designer of the agent.

Perception is the conversion of a sensor signal into a description of the environment. The description is what later steps can retrieve.

Natural language is human language in text or in speech. A question and an answer are both pieces of natural language.

Planning is the selection of a sequence of actions before those actions are taken. The sequence is a plan.

Search is a method that tries actions until a goal state is reached. Each try moves from one state to another state.

A state is one configuration of a problem. The start state is the configuration where search begins.

An action is a move from one state to another state. The cost of an action is a number stored with that move.

A goal is a state that the problem counts as success. Search stops when it reaches a goal.

A heuristic is a stored estimate of the remaining cost to a goal. The estimate guides which state to try next.

Breadth-first search is a search that finishes every state at the current depth before the next depth. It finds a shortest path when every action has the same cost.

Depth-first search is a search that follows one path as far as that path can go. It uses less memory than breadth-first search and can miss a shorter path.

A star search is a search that orders states by the path cost plus a heuristic. The heuristic must not overestimate the remaining cost.

A knowledge base is a store of sentences a program can retrieve. A later question reads those sentences instead of inventing a new one.

A proposition is a sentence that is either true or false. The sentence names a subject, a relation, and an object.

Inference is the derivation of a sentence from sentences already stored. The new sentence is kept only when a rule produces it.

A rule is a sentence that names what follows when a condition holds. The condition and the consequence are both stored text.

Logic is a system of rules for inference. The rules do not add a fact that no stored sentence supports.

A dataset is a stored collection of examples. Each example is one input, and some examples also store the correct output.

A feature is one measured property of an example. Color, length, and a word count are features.

A label is the correct output stored with a supervised example. The label is the answer the example already carries.

Machine learning is a method that sets numeric parameters from examples. The parameters are numbers inside a model.

Supervised learning is learning from examples that already name the correct output. The correct output is the label.

Unsupervised learning is learning from examples that do not name a correct output. The method looks for structure in the inputs alone.

Reinforcement learning is learning from a reward that follows an action. The reward is a number, not a full label for every step.

A training set is the collection of examples used to set parameters. Those examples are the ones the procedure is allowed to fit.

A test set is a collection of examples kept out of training. The test set measures behavior on examples the fit did not see.

Validation is the use of held-out examples to choose a model. The choice happens before the final test.

A model is a stored function from an input to an output. The function is fixed once training stops.

A parameter is a number that training is allowed to change. A weight in a network is a parameter.

A classifier is a model that assigns an example to one class. The class is the label the model predicts.

A regression model is a model that predicts a number. The number is the output of the function.

Overfitting is a fit that matches the training set and fails on new examples. The fit has memorized the training examples.

Underfitting is a fit that fails on the training set and also fails on new examples. The model is too weak for the task.

Generalization is correct behavior on examples the training set did not contain. A useful model generalizes.

A neural network is a model built from layers of numeric units. Each unit computes a number from the numbers it receives.

A layer is a group of units that transforms one vector into another vector. The next layer reads that new vector.

A loss is a number that measures the distance between a prediction and a stored target. Training tries to make the loss smaller.

Gradient descent is a procedure that changes parameters in order to reduce a loss. Each step moves the parameters by a small amount.

An embedding is a numeric vector that stands for a word or a passage. Nearby vectors stand for related text.

Similarity is the closeness of two embeddings in that vector space. Retrieval uses that closeness to pick a passage.

A token is a piece of text that a model treats as one unit. A word or a word piece can be a token.

A transformer is a neural network that relates each token to other tokens in the same sequence. The relation is computed from the embeddings of those tokens.

A language model is a model that assigns a probability to a sequence of tokens. The probability is a number for that sequence.

Generation is the production of a new token sequence from a language model. The new sequence is not a sentence copied from the store.

Retrieval is the selection of stored passages that match a question. The selected passage is text the index already holds.

A chunk is one paragraph stored as its own row in the index. A question retrieves chunks, not a whole book at once.

A grounded answer is a sentence built from a passage the index already stores. The words of that sentence come from the stored passage.

A hallucination is a generated sentence that the stored passages do not support. A grounded engine withholds that sentence.

Accuracy is the share of examples that a model labels correctly. The share is counted on a named set of examples.

A benchmark is a fixed set of examples used to compare methods. The set stays the same across the comparison.

Bias is a systematic error that favors one group of examples over another group. The error remains after one lucky example is removed.

Alignment is the match between a system's behavior and the behavior a person requested. A gap in that match is an alignment problem.

Compute is the numeric work a processor performs to train a model or to run a model. More parameters usually require more compute.

A graphics processor is hardware built to run many numeric operations at the same time. Training a large neural network often uses that hardware.

A central processor is the general processor inside a computer. A question in cpu-llm is answered on a central processor.

cpu-llm is a text engine that answers from stored paragraphs on a central processor. It does not sample the next token from a decoder.

VectorPrism is the encoder that stores each paragraph as one numeric tensor. The tensor is what retrieval compares with the question.

pgvector is the PostgreSQL extension that stores those tensors for cpu-llm. Each tensor sits in the same row as its paragraph.

The realizer is the part of cpu-llm that rebuilds one sentence from a stored proposition. The rebuilt sentence has to match the stored sentence.

The auditor is the check that the rebuilt sentence still matches that proposition. A failed check withholds the sentence.

WikiText is a collection of Wikipedia articles shipped beside this primer. The articles and this primer share one index.

Deep search is a cpu-llm mode that keeps every stored paragraph the question words can reach. The kept paragraphs are returned as possibilities.

A comparison in cpu-llm is a reply that places the stored sentences of two topics side by side. The reply does not invent a sentence that says how the topics differ.

A summary in cpu-llm is a short selection of stored sentences ordered by their epistemic weight. A contradiction removes the summary.
