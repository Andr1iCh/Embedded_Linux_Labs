#include <linux/errno.h>
#include <linux/fs.h>
#include <linux/init.h>
#include <linux/miscdevice.h>
#include <linux/module.h>
#include <linux/printk.h>
#include <linux/uaccess.h>

static int dev_open(struct inode *inode, struct file *file)
{
	/* Для запису тривоги не потрібні окремі дані відкритого файла. */
	return 0;
}

static ssize_t dev_write(struct file *file, const char __user *buffer,
			 size_t length, loff_t *offset)
{
	char command;

	/* Порожній запис нічого не робить. Команда має складатися з одного байта. */
	if (length == 0)
		return 0;
	if (length != 1)
		return -EINVAL;

	/* Копіюємо байт із пам'яті програми до змінної в ядрі. */
	if (copy_from_user(&command, buffer, 1))
		return -EFAULT;
	if (command != '1')
		return -EINVAL;

	pr_alert("[SDR KERNEL ALERT] Critical Signal Level Detected!\n");
	return length;
}

static int dev_release(struct inode *inode, struct file *file)
{
	/* При закритті файла немає виділених ресурсів, які треба звільнити. */
	return 0;
}

static const struct file_operations alert_ops = {
	.owner = THIS_MODULE,
	.open = dev_open,
	.write = dev_write,
	.release = dev_release,
};

static struct miscdevice alert_device = {
	.minor = MISC_DYNAMIC_MINOR,
	.name = "sdr_alert",
	.fops = &alert_ops,
	.mode = 0600,
};

static int __init sdr_alert_init(void)
{
	int result;

	/* Реєструємо символьний пристрій із динамічним номером minor. */
	result = misc_register(&alert_device);
	if (result < 0)
		return result;

	pr_info("[SDR KERNEL] Registered /dev/sdr_alert\n");
	return 0;
}

static void __exit sdr_alert_exit(void)
{
	/* Прибираємо реєстрацію пристрою під час вивантаження модуля. */
	misc_deregister(&alert_device);
	pr_info("[SDR KERNEL] Unregistered /dev/sdr_alert\n");
}

module_init(sdr_alert_init);
module_exit(sdr_alert_exit);

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("SDR signal level alert");
