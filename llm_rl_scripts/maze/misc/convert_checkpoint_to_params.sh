export TOKENIZERS_PARALLELISM=false
export GOOGLE_APPLICATION_CREDENTIALS=""
export GCLOUD_PROJECT=""
git config --global --add safe.directory 
sudo rm -r /tmp/*tpu*
export maze_name="double_t_maze"
export checkpoint_path=""
python -m examples_jaxseq.misc.export_checkpoint my_checkpoint_path