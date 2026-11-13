import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler

class Autoencoder(nn.Module):
    def __init__(self, input_dim, latent_dim=8):
        super().__init__()
        self.encoder = nn.Sequential(nn.Linear(input_dim, 32), nn.ReLU(), nn.Linear(32, 16), nn.ReLU(), nn.Linear(16, latent_dim))
        self.decoder = nn.Sequential(nn.Linear(latent_dim, 16), nn.ReLU(), nn.Linear(16, 32), nn.ReLU(), nn.Linear(32, input_dim))

    def forward(self, x):
        return self.decoder(self.encoder(x))

class AEDetector:
    def __init__(self, latent_dim=8, epochs=80, lr=1e-3, batch_size=64, random_state=42):
        torch.manual_seed(random_state)
        self.latent_dim = latent_dim
        self.epochs = epochs
        self.lr = lr
        self.batch_size = batch_size
        self.scaler = StandardScaler()
        self.model = None
        self.threshold = None
        self.feature_names_ = None

    def fit(self, X_clean):
        self.feature_names_ = list(X_clean.columns)
        Xs = self.scaler.fit_transform(X_clean)
        Xs_t = torch.tensor(Xs, dtype=torch.float32)
        loader = DataLoader(TensorDataset(Xs_t), batch_size=self.batch_size, shuffle=True)
        self.model = Autoencoder(Xs.shape[1], self.latent_dim)
        opt = torch.optim.Adam(self.model.parameters(), lr=self.lr)
        loss_fn = nn.MSELoss()

        self.model.train()
        for _ in range(self.epochs):
            for (batch,) in loader:
                opt.zero_grad()
                out = self.model(batch)
                loss = loss_fn(out, batch)
                loss.backward()
                opt.step()

        self.model.eval()
        with torch.no_grad():
            recon = self.model(Xs_t)
            errors = ((recon - Xs_t) ** 2).mean(dim=1).numpy()
        self.threshold = float(np.percentile(errors, 95))
        return self

    def score(self, X):
        Xs = self.scaler.transform(X[self.feature_names_])
        Xs_t = torch.tensor(Xs, dtype=torch.float32)
        self.model.eval()
        with torch.no_grad():
            recon = self.model(Xs_t)
            errors = ((recon - Xs_t) ** 2).mean(dim=1).numpy()
        return errors

    def predict(self, X):
        return (self.score(X) > self.threshold).astype(int)
