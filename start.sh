sudo rm -rf /boot/efi/grub

grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=GRUB --recheck

grub-mkconfig -o /boot/grub/grub.cfg

sudo pacman -S os-prober

sudo os-prober

sudo pacman -S git base-devel

sudo pacman -S wget curl make cmake nano vim

git clone https://github.com/caelestia-dots/caelestia.git ~/.local/share/caelestia

fish ~/.local/share/caelestia/install.fish


