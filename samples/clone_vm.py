#!/usr/bin/env python
"""
Written by Dann Bohn
Github: https://github.com/whereismyjetpack
Email: dannbohn@gmail.com

Clone a VM from template example
"""
from pyVmomi import vim
from tools import cli, service_instance, pchelper

from add_nic_to_vm import add_nic


def wait_for_task(task):
    """ wait for a vCenter task to finish """
    task_done = False
    while not task_done:
        if task.info.state == 'success':
            return task.info.result

        if task.info.state == 'error':
            print("there was an error")
            print(task.info.error)
            task_done = True


def clone_vm(
        content, template, vm_name, datacenter_name, vm_folder, datastore_name,
        cluster_name, resource_pool, power_on, datastorecluster_name):
    """
    Clone a VM from a template/VM, datacenter_name, vm_folder, datastore_name
    cluster_name, resource_pool, and power_on are all optional.
    """

    # If no data center name is provided, get the default first data center
    if datacenter_name:
        datacenter = pchelper.get_obj(content, [vim.Datacenter], datacenter_name)
    else:
        datacenters = content.rootFolder.childEntity  
        for dc in datacenters:
            if isinstance(dc, vim.Datacenter):  
                datacenter = dc  
                print(f"Automatically selected data center: {datacenter.name}")
                break
        else:
            raise RuntimeError("No data centers found")

            

    if vm_folder:
        destfolder = pchelper.search_for_obj(content, [vim.Folder], vm_folder)
    else:
        destfolder = datacenter.vmFolder

    if datastore_name:
        datastore = pchelper.search_for_obj(content, [vim.Datastore], datastore_name)
    else:
        datastore = pchelper.get_obj(
            content, [vim.Datastore], template.datastore[0].info.name)

    # if None, get the first one
    cluster = pchelper.search_for_obj(content, [vim.ClusterComputeResource], cluster_name)
    if not cluster:
        clusters = pchelper.get_all_obj(content, [vim.ResourcePool])
        cluster = list(clusters)[0]

    if resource_pool:
        resource_pool = pchelper.search_for_obj(content, [vim.ResourcePool], resource_pool)
    else:
        resource_pool = cluster.resourcePool

    vmconf = vim.vm.ConfigSpec()

    if datastorecluster_name:
        podsel = vim.storageDrs.PodSelectionSpec()
        pod = pchelper.get_obj(content, [vim.StoragePod], datastorecluster_name)
        podsel.storagePod = pod

        storagespec = vim.storageDrs.StoragePlacementSpec()
        storagespec.podSelectionSpec = podsel
        storagespec.type = 'create'
        storagespec.folder = destfolder
        storagespec.resourcePool = resource_pool
        storagespec.configSpec = vmconf

        try:
            rec = content.storageResourceManager.RecommendDatastores(
                storageSpec=storagespec)
            rec_action = rec.recommendations[0].action[0]
            real_datastore_name = rec_action.destination.name
        except Exception:
            real_datastore_name = template.datastore[0].info.name

        datastore = pchelper.get_obj(content, [vim.Datastore], real_datastore_name)

    # set relospec
    relospec = vim.vm.RelocateSpec()
    relospec.datastore = datastore
    relospec.pool = resource_pool

    clonespec = vim.vm.CloneSpec()
    clonespec.location = relospec
    clonespec.powerOn = power_on

    print("cloning VM...")
    task = template.Clone(folder=destfolder, name=vm_name, spec=clonespec)
    wait_for_task(task)
    print("VM cloned.")


def main():
    """
    Let this thing fly
    """
    parser = cli.Parser()
    parser.add_required_arguments(cli.Argument.VM_NAME, cli.Argument.TEMPLATE)
    # if no locationis provided, thefirst available datacenter, datastore, etc. will be used
    parser.add_optional_arguments(cli.Argument.DATACENTER_NAME, cli.Argument.VMFOLDER,
                                  cli.Argument.DATASTORE_NAME, cli.Argument.DATASTORECLUSTER_NAME,
                                  cli.Argument.CLUSTER_NAME, cli.Argument.RESOURCE_POOL,
                                  cli.Argument.POWER_ON, cli.Argument.OPAQUE_NETWORK_NAME)
    args = parser.get_args()
    si = service_instance.connect(args)

    content = si.RetrieveContent()
    template = pchelper.get_obj(content, [vim.VirtualMachine], args.template)

    if template:
        clone_vm(
            content, template, args.vm_name, args.datacenter_name, args.vm_folder,
            args.datastore_name, args.cluster_name, args.resource_pool, args.power_on,
            args.datastorecluster_name)
        if args.opaque_network_name:
            vm = pchelper.get_obj(content, [vim.VirtualMachine], args.vm_name)
            add_nic(si, vm, args.opaque_network_name)
    else:
        print("template not found")


# start this thing
if __name__ == "__main__":
    main()
