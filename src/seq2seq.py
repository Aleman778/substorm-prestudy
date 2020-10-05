import spacy
import numpy as np
import random
import torch
import torch.nn as nn
import torch.nn.functional as F
from tqdm import tqdm

class Seq2Seq(nn.Module):
    def __init__(self, embedding_size, hidden_size):
        super(Seq2Seq, self).__init__()
        self.enc_cell = nn.GRU(input_size=embedding_size, hidden_size=hidden_size)
        self.enc_dropout = nn.Dropout(0.5)
        self.dec_cell = nn.GRU(input_size=embedding_size, hidden_size=hidden_size)
        self.dec_dropout = nn.Dropout(0.5)
        self.fc = nn.Linear(hidden_size, embedding_size)

    def forward(self, enc_inputs, enc_hidden, dec_inputs):
        batch_size = enc_inputs.shape[1]
        num_steps = enc_inputs.shape[0]
        enc_inputs = self.enc_dropout(enc_inputs.transpose(0, 1))
        dec_inputs = self.dec_dropout(dec_inputs.transpose(0, 1))

        _, enc_state = self.enc_cell(enc_inputs, enc_hidden)
        dec_outputs, _ = self.dec_cell(dec_inputs, enc_state)
        dec_outputs = dec_outputs.transpose(0, 1)

        outputs = torch.zeros(num_steps, batch_size, embedding_size).to(device)
        for i in range(num_steps):
            outputs[i] = self.fc(dec_outputs[i])
        return outputs

    def forward_without_teacher(self, enc_inputs, enc_hidden):
        batch_size = enc_inputs.shape[0]
        num_steps = enc_inputs.shape[1]
        enc_inputs = self.enc_dropout(enc_inputs.transpose(0, 1))
        _, enc_state = self.enc_cell(enc_inputs, enc_hidden)

        dec_inputs = torch.FloatTensor([[keywords["<START>"]]*batch_size]).to(device)
        # dec_inputs = dec_inputs.transpose(0, 1)

        outputs = torch.zeros(num_steps, batch_size, embedding_size).to(device)
        for i in range(num_steps):
            dec_outputs, enc_state = self.dec_cell(dec_inputs, enc_state)
            outputs[i] = self.fc(dec_outputs)
            dec_inputs = outputs[i].unsqueeze(0)
        return outputs

def extract_word_embeddings(nlp, keywords, text):
    result = []
    for entry in text:
        doc = nlp(entry)
        vectors = []
        i = 0
        while i < len(doc):
            if doc[i].text == "<" and doc[i + 2].text == ">":
                if ("<" + doc[i + 1].text + ">") in keywords:
                    vectors.append(keywords["<" + doc[i + 1].text + ">"])
                    i += 3
                    continue
            if doc[i].is_oov:
                nlp.vocab.set_vector(doc[i].text, np.random.uniform(-10, 10, (300,)))
                print(doc[i].text, "is out-of-vocabulary")
            vectors.append(doc[i].vector)
            i += 1
        result.append(vectors)
    return result
                
def correct_vector_length(vectors, target_length, pad_vector):
    result = []
    for v in vectors:
        while len(v) > target_length: # Split into two entries
            sub = v[:target_length]
            v = v[target_length + 1:]
            result.append(sub)
        if len(v) == 0: 
            continue
        if len(v) == target_length: # Perfect this one is done
            result.append(v)
        else: # Add padding to reach the targe length
            for i in range(target_length-len(v)):
                v.append(pad_vector)
            result.append(v)
    return result

if __name__ == "__main__":
    # Hyper-parameters (tunable parameters to improve training)
    lr_rate = 0.001 # factor of how much the network weights should change per training batch.
    num_epochs = 5000 # number of times to train (i.e. change weights) the model.
    num_steps = 10 # the number of words that can appear in sequence.
    embedding_size = 300 # the size of vectors, spaCy uses 300 dimensions for their embeddings.
    hidden_size = 512 # size of the hidden state in RNN, chosen arbitrarily.

    # Find device, 
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Using device: " + torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU");
    
    # Seting up the dataset
    nlp = spacy.load("en_core_web_md")
    dataset_inputs  = ["Email alemen-6@student.ltu.se saying Hello world.",
                       "Send email to my friend, I am about 15 minutes late for school."
                       "I am about 15 minutes late for work, send email to my colleagues"]
    dataset_outputs = ["email <TO> alemen-6@student.ltu.se <BODY> Hello world!",
                       "email <TO> my friend <BODY> I am about 15 minutes late for school.",
                       "email <TO> my colleagues <BODY> I am about 15 minutes late for work."]

    # Add custom vectors for tagging stuff
    keywords = {"<START>": np.random.uniform(-1, 1, (300,)),
                "<END>": np.random.uniform(-1, 1, (300,)),
                "<TO>": np.random.uniform(-1, 1, (300,)),
                "<BODY>": np.random.uniform(-1, 1, (300,)),
                "<PAD>": np.random.uniform(-1, 1, (300,))}
    for word, vector in keywords.items():
        nlp.vocab.set_vector(word, vector)
    # TODO(alexander): These needs to be stored so we can interpret future uses of this model


    # Separate dataset outputs (inputs to decoder) and its target
    dataset_targets = []
    for i in range(len(dataset_outputs)):
        dataset_targets.append(dataset_outputs[i] + " <END>");
        dataset_outputs[i] = "<START> " + dataset_outputs[i]
    
    # Convert sentences into vectors of words
    input_vectors = extract_word_embeddings(nlp, keywords, dataset_inputs)
    output_vectors = extract_word_embeddings(nlp, keywords, dataset_outputs)
    target_vectors = extract_word_embeddings(nlp, keywords, dataset_targets)

    # Make sure that each sentence have num_steps vectors, add padding if needed
    # NOTE: the neural network requires sequences to have the same dimensions, strict requirement.
    input_vectors = correct_vector_length(input_vectors, num_steps, keywords["<PAD>"])
    output_vectors = correct_vector_length(output_vectors, num_steps, keywords["<PAD>"])
    target_vectors = correct_vector_length(target_vectors, num_steps, keywords["<PAD>"])

    # print("inputs: ", end='')
    # result = ""
    # for ent in input_vectors:
    #     for v in ent: 
    #         keys, _, _ = nlp.vocab.vectors.most_similar(v.reshape(1, v.shape[0]))
    #         for k in keys:
    #             text = nlp.vocab[k[0]].text
    #             result += text + " "
    # print(result.encode("utf-8"))
        
    # print("outputs: ", end='')
    # result = ""
    # for ent in output_vectors:
    #     for v in ent: 
    #         keys, _, _ = nlp.vocab.vectors.most_similar(v.reshape(1, v.shape[0]))
    #         for k in keys:
    #             text = nlp.vocab[k[0]].text
    #             result += text + " "
    # print(result.encode("utf-8"))
        
    # print("targets: ", end='')
    # result = ""
    # for ent in target_vectors:
    #     for v in ent: 
    #         keys, _, _ = nlp.vocab.vectors.most_similar(v.reshape(1, v.shape[0]))
    #         for k in keys:
    #             text = nlp.vocab[k[0]].text
    #             result += text + " "
    # print(result.encode("utf-8"))
    # exit(0)

    # Setting up the model (criterion/optimizare are also hyper-parameters)
    model = Seq2Seq(embedding_size, hidden_size)
    criterion = nn.MSELoss() # TODO(alexander); don't know if this is good loss to use
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    # Training loop
    filename = "seq2seq_checkpoint.pt" # used for saving/loading trained models
    if True:
        print("Training started")
        lowest_loss = 10
        model = model.to(device)
        pbar = tqdm(range(num_epochs))
        for epoch in pbar:
            l = len(input_vectors)
            # Pick a random sample from the training set
            # idx = epoch % len(input_vectors)
            inputs = torch.FloatTensor(input_vectors[:l]).to(device)
            hidden = torch.FloatTensor(torch.zeros(1, l, hidden_size)).to(device)
            outputs = torch.FloatTensor(output_vectors[:l]).to(device)
            targets = torch.FloatTensor(target_vectors[:l]).to(device)

            optimizer.zero_grad() # resets the gradiens from previous epoch
            predictions = model(inputs, hidden, outputs)
            loss = criterion(predictions, targets)
            loss.backward();
            optimizer.step();
            epoch_loss = loss.item()

            if (epoch % 20) == 0:
                pbar.set_description("Training model - loss: %.6f" % epoch_loss)

            if (epoch % 100) == 0:
                if epoch_loss < lowest_loss:
                    torch.save(model.state_dict(), filename)
                    lowest_loss = epoch_loss
                    print("Reached lower loss of %.6f at epoch %d saving to %s" % (lowest_loss, epoch + 1, filename))
        print("Training ended")
    else:
        print("Loading previously trained model...")
        model.load_state_dict(torch.load(filename))
        print("Loaded `" + filename + "` model successfully.")

    # Testing the model
    if True:
        print("Testing the model")
        model = model.to(device)
        model.eval(); # Ignore dropout
        with torch.no_grad(): # Ignore gradient calculations, lower memory footprint
            # test = input("> ").split(' ')
            test_text = ["Send an email with information about my project to my group members"]
                         # "Email alemen-6@student.ltu.se saying Hello world!.",
                         # "Send email to my friend, I'm about 15 minutes late for school."]
            print("input:", test_text)

            # Preprocess
            test_vectors = extract_word_embeddings(nlp, keywords, test_text)
            max_len = 0
            for v in test_vectors:
                if len(v) > max_len:
                    max_len = len(v)
            print("Max length:", max_len)

            for v in test_vectors:
                while len(v) < max_len:
                    v.append(keywords["<PAD>"])

            pad_text = ["<START>" + " <PAD>"*(max_len - 1)]
                        # "<START>" + " <PAD>"*(max_len - 1),
                        # "<START>" + " <PAD>"*(max_len - 1)]
            pad_vectors = extract_word_embeddings(nlp, keywords, pad_text)

            test_vectors = correct_vector_length(test_vectors, num_steps, keywords["<PAD>"])
            pad_vectors = correct_vector_length(pad_vectors, num_steps, keywords["<PAD>"])

            # Create tensors for pytorch
            inputs = torch.FloatTensor(test_vectors).to(device)
            hidden = torch.FloatTensor(torch.zeros(1, len(test_vectors), hidden_size)).to(device)
            padding = torch.FloatTensor(pad_vectors).to(device)

            print("output: ", end='')
            found_end_token = False;
            tries = 1
            while not found_end_token and tries > 0:
                tries -= 1
                outputs = model.forward_without_teacher(inputs, hidden).cpu()

                # Next it remove start
                # pad_text = "<PAD>"
                # pad_vectors = extract_word_embeddings(nlp, keywords, [pad_text])
                # pad_vectors = correct_vector_length(pad_vectors, num_steps, keywords["<PAD>"])
                # padding = torch.FloatTensor([pad_vectors[0]]).to(device)

                for v in outputs:
                    keys, _, _ = nlp.vocab.vectors.most_similar(v, n=10)
                    for k in keys:
                        result = ""
                        text = nlp.vocab[k[0]].text
                        if text == "<END>":
                            found_end_token = True;
                            break;
                        for i in range(10):
                            result += nlp.vocab[k[i]].text + ", "
                        print("- ", result.encode("utf-8"))
            print("")
    print("Exiting the program")
