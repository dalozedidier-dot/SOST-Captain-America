# Tutorials

To validate notebooks from a clean environment:

```bash
python -m pip install -r requirements.txt  # if present
python -m pip install jupyter nbconvert
jupyter nbconvert --execute --to notebook --inplace tutorials/01_demo_transition_systemique.ipynb
```

The notebooks are expected to run end-to-end with a fresh kernel.
