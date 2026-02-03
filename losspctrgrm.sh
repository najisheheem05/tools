mkdir -p spectrograms

./lossflag.sh ~/Music/Test | while read -r f; do
  sox "$f" -n spectrogram -r -o "spectrograms/$(basename "${f%.flac}").png"
done
