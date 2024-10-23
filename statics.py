import os, sys, ujson
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import networkx as nx
import subprocess
import numpy as np

from MSCCDTaskData import *

def divideCloneListByGranularity(cloneList):
    fileLevelCloneList = []
    blockLevelCloneList = []
    
    for clonePair in cloneList:
        tokenBagA = tokenBagList[clonePair[0][0]][clonePair[0][1]][clonePair[0][2]]
        tokenBagB = tokenBagList[clonePair[1][0]][clonePair[1][1]][clonePair[1][2]]
        
        if tokenBagA["granularity"] == 0 and tokenBagB["granularity"] == 0:
            fileLevelCloneList.append(clonePair)
        else:
            blockLevelCloneList.append(clonePair)
    
    return fileLevelCloneList, blockLevelCloneList


def get_code_line_count_project(project_path):
    try:
        process = subprocess.Popen(
            ["cloc","--json",project_path,"--timeout","0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        output, errors = process.communicate()

        if errors:
            print(f"Errors: {errors}")

        outputObj = ujson.loads(output)
        return outputObj['SUM']['code']
    except Exception as e:
        print(f"An error occurred: {e}")
        return 0

def drawProjectsGraph(allData, savePath):
    # 创建无向图
    G = nx.Graph()

    # 添加节点，并设置节点的大小和标签
    for node, details in allData["elements"].items():
        size, label = details
        G.add_node(node, size=size*300, label=label)  # 调整面积缩放因子以改善视觉显示

    # 添加边，同时记录原始权重
    for node, edges in allData["data"].items():
        for adjacent, weight in edges.items():
            if weight > 0:
                G.add_edge(node, adjacent, weight=np.log(weight + 1), original_weight=weight)  # 使用对数权重，+1以避免对数0的问题

    # 非平面图对应
    # 检查图是否是平面图
    is_planar, _ = nx.check_planarity(G)
    # is_planar = False
    # print(f"Is the graph planar? {is_planar}")

    # 绘制图形
    if is_planar:
        pos = nx.planar_layout(G)  # 使用平面布局
    else:
        pos = nx.spring_layout(G) # 使用弹簧布局
    sizes = [G.nodes[node]['size'] for node in G]  # 获取节点的大小
    labels = {node: G.nodes[node]['label'] for node in G}  # 获取节点的标签
    weights = [G[u][v]['weight']*2 for u, v in G.edges()]  # 获取边的权重，并调整缩放

    nx.draw(G, pos, labels=labels, with_labels=True, node_color='skyblue', node_size=sizes, width=weights, font_size=15, font_color='darkred')

    # # 调整标签位置
    # for node, (x, y) in pos.items():
    #     plt.text(x, y, s=G.nodes[node]['label'], fontsize=10, ha='right' if x < 0.5 else 'left', color='darkred')

    # 添加边的原始权重标签
    edge_labels = {(u, v): G[u][v]['original_weight'] for u, v in G.edges()}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, label_pos=0.6)  # 调整label_pos来改变标签位置

    # plt.show()
    plt.savefig(savePath, format="pdf", dpi=300)  # 保存为PDF文件
    plt.clf()  # 清空图形    

def addItemsIntoSetFromSet(setA, setB):
    for item in setB:
        setA.add(item)
    return setA


## This function is used to generate 2 set for each task, one contains the proj id with less than 1000 commits,and one contains the proj id with more than 1000 commits
## The input is the path of the pre-generated json file that contains the commit number for each project
def generateDictForCommitNumFilter(sourcePath):
    res = {}
    
    commitNumDict = ujson.load(open(sourcePath, "r"))
    
    taskIdList = list(range(20001,20021))
    
    for taskId in taskIdList:
        taskId = str(taskId)
        
        configObj = getConfigObj(taskId)
        
        res[taskId] = {"lessThan1000": set(), "moreThan1000": set()} 

        for projname_lang_item in commitNumDict['taskId'][taskId]:
            projName = projname_lang_item[0]
            lang = projname_lang_item[1]
            
            projId = getProjIdByProjName(configObj, projName)
            commitNum = int(commitNumDict['projInfo'][lang][projName]['commitNum'])
            
            if commitNum < 1000:
                res[taskId]["lessThan1000"].add(projId)
            else:
                res[taskId]["moreThan1000"].add(projId)
    
    return res

def filterCloneListByCommitNum(cloneClassListToFilter, commitNumFilterDict, type): # type: "lessThan1000" or "moreThan1000"
    res = []
        
    for cloneClass in cloneClassListToFilter:
        num_lessThan1000 = 0
        num_moreThan1000 = 0
        
        for codeSegment in cloneClass:
            if codeSegment[0] in commitNumFilterDict['lessThan1000']:
                num_lessThan1000 += 1
            elif codeSegment[0] in commitNumFilterDict['moreThan1000']:
                num_moreThan1000 += 1

        
        if type == "lessThan1000":
            if num_lessThan1000 == len(cloneClass):
                res.append(cloneClass)        
        
        elif type == "moreThan1000":
            if num_moreThan1000 == len(cloneClass):
                res.append(cloneClass)

        
        elif type == "both":
            if 0 < num_lessThan1000 and 0 < num_moreThan1000:
                res.append(cloneClass)
                
            # else:
            #     if num_lessThan1000 == len(cloneClass) or num_moreThan1000 == len(cloneClass):
            #         pass
            #     else:
            #         print(str(num_lessThan1000) + " " + str(num_moreThan1000))
        
                
        # if clonePair[0][0] in commitNumFilterDict[key] and clonePair[1][0] in commitNumFilterDict[key]:
        #     res.append(clonePair)
    
    return res
    
    
    
     

## Some repositories are included in mutiple tasks, so we need to remove the overlapped clone pairs and clone classes
## This dictionary is used to store the overlapped projects for each task when tring to remove the overlapped clone pairs and clone classes
OVERLAPPED_PROJECTS = { # taskId: {projectId}
    20002: {8},
    20009: {0},
    20012: {0,1,2,3},
    20015: {0},
    20019: {0,1,2,3,4,5},
    20020: {0,1,2,3,4},
    20001:{},20003:{},20004:{},20005:{},20006:{},20007:{},20008:{},20010:{},20011:{},20013:{},20014:{},20015:{},20016:{},20017:{},20018:{}
}




if __name__ == "__main__":

    
    detectionId = sys.argv[1]  # 1: original results (no clone divisions), 5: results with clone divisions 6: results after filtering
    commitFilter = sys.argv[2] # "lessThan1000", "moreThan1000", "both"
    
    taskIdList = list(range(20001,20021))
    ### We do not calculate the following tasks in C#, because there are a lot of file parsing errors that result in many false positive clones (both intra-project and cross-project) and hard to remove them automatically.
    taskIdList.remove(20013)
    taskIdList.remove(20014)
    taskIdList.remove(20015)
    
    
    commitNumFilterDict = generateDictForCommitNumFilter("./commitNum.json")
    projectSizeDict = ujson.loads(open("./projectSizeDict.json", "r").read())
    
    # taskIdList = [20021]
    
    all_project_set = set()

    ## Project with clones
    all_projectWithClone_set = set()
    all_projectWithClone_fileLevel_set = set()
    all_projectWithClone_blockLevel_set = set()
    
    ## Project with corss-project clones
    all_projectWithCrossProjectClone_set = set()
    all_projectWithCrossProjectClone_fileLevel_set = set()
    all_projectWithCrossProjectClone_blockLevel_set = set()
    
    ## Pair of cross-project clones
    all_crossProjectClone_num = 0
    all_crossProjectClone_fileLevel_num = 0
    all_crossProjectClone_blockLevel_num = 0
    
    ## Pair of intra-project clones
    all_intraProject_clone_num = 0
    all_intraProjectClone_fileLevel_num = 0
    all_intraProjectClone_blockLevel_num = 0
    
    
    ## Clone Classes contains cross-project clones
    all_clone_class_num = 0
    all_clone_class_fileLevel_num = 0
    all_clone_class_blockLevel_num = 0
    
    ## Clone Classes contains cross-project clones
    all_crossProjectClone_class_num = 0
    all_crossProjectClone_class_fileLevel_num = 0
    all_crossProjectClone_class_blockLevel_num = 0
    
    ## For Mean cross-project clone size
    all_crossProjectClone_meanSize = 0
    all_crossProjectClone_fileLevel_meanSize = 0
    all_crossProjectClone_blockLevel_meanSize = 0
    
    ## For Mean intra-project clone size
    all_intraProjectClone_meanSize = 0
    all_intraProjectClone_fileLevel_meanSize = 0
    all_intraProjectClone_blockLevel_meanSize = 0
    
    ## For Mean segments of all clone classes 
    all_clone_class_segments_num = 0
    all_clone_class_fileLevel_segments_num = 0
    all_clone_class_blockLevel_segments_num = 0
    
    ## For Mean segments of clone classes contains cross-project clones
    all_crossProjectClone_class_segments_num = 0
    all_crossProjectClone_class_fileLevel_segments_num = 0
    all_crossProjectClone_class_blockLevel_segments_num = 0
    
    
    size_all_clone_mean = 0
    
    
    print("taskId, crossProjectClone_FileLevel_Num, crossProjectClone_BlockLevel_Num, crossProjectClone_fileLevel_num_kloc, crossProjectClone_blockLevel_num_kloc, crossProjectClone_class_fileLevel_num, crossProjectClone_class_blockLevel_num, crossProjectClone_class_fileLevel_segments_meanNum, crossProjectClone_class_blockLevel_segments_meanNum")
    for taskId in taskIdList:
        # Get details for the task
        
        fileList = fileListGeneration(taskId)
        cloneList = cloneListGeneration(taskId, detectionId)
        cloneClassList = cloneClassListGeneration(taskId, detectionId)
        
        ## to remove the clone class with less than 3 segments
        ## class.file includes the clone class that only contains one pair that do not meet the difinition of clone division
        tmp = []
        for item in cloneClassList:
            if len(item) >= 3:
                tmp.append(item)
        cloneClassList = tmp
        
        # print(str(len(cloneClassList)))
        
        if commitFilter == "lessThan1000":
            # to only calculate the clone pairs between projects with less than 1000 commits
            cloneList = filterCloneListByCommitNum(cloneList, commitNumFilterDict[str(taskId)], "lessThan1000")
            cloneClassList = filterCloneListByCommitNum(cloneClassList, commitNumFilterDict[str(taskId)], "lessThan1000")
        elif commitFilter == "moreThan1000":
            # to only calculate the clone pairs between projects with more that 1000 commits
            cloneList = filterCloneListByCommitNum(cloneList, commitNumFilterDict[str(taskId)], "moreThan1000")
            cloneClassList = filterCloneListByCommitNum(cloneClassList, commitNumFilterDict[str(taskId)], "moreThan1000")
        elif commitFilter == "both":
            # between two situations
            cloneList = filterCloneListByCommitNum(cloneList, commitNumFilterDict[str(taskId)], "both")
            cloneClassList = filterCloneListByCommitNum(cloneClassList, commitNumFilterDict[str(taskId)], "both")
        
        # print(str(len(cloneClassList)))
        
        # ## to remove the overlapped clone pairs 
        # tmp = []
        # for item in cloneList:
        #     if not item[0][0] in OVERLAPPED_PROJECTS[int(taskId)] and not item[1][0] in OVERLAPPED_PROJECTS[int(taskId)]:
        #         tmp.append(item)
        # cloneList = tmp
        
        # ## to remove the overlapped clone classes
        # tmp = []
        # for item in cloneClassList:
        #     flag = False
        #     for codeSegment in item:
        #         if codeSegment[0] not in OVERLAPPED_PROJECTS[taskId]:
        #             flag = True
        #             break
        #     if flag:
        #         tmp.append(item)
        # cloneClassList = tmp
        

        
        ## to get clone class contains cross-project clones
        crossProjectCloneClass_list = []
        for cloneClass in cloneClassList:
            projectId_set = set()
            for codeSegment in cloneClass:
                projectId_set.add(codeSegment[0])
            if len(projectId_set) > 1:
                crossProjectCloneClass_list.append(cloneClass)
            else:
                print("!!!!!!!!!!!!!!!!" + taskId)
        
        tokenBagList = tokenBagListGeneration(taskId)
        
        if (len(crossProjectCloneClass_list) != len(cloneClassList)):
            print("!!!!!!!!!!!!!!!!" + taskId)

        

                
        # To calculate the project num        
        configObj = getConfigObj(taskId)
        language = configObj['tokenizer']
        projectList = configObj['inputProject']
        for projectIndex in range(len(projectList)):
            all_project_set.add(language + os.path.basename(projectList[projectIndex]))

        
        
        
        # Clone Class Nums and Clone Class Sizes

        clone_class_num = len(cloneClassList)
        clone_class_fileLevel_num = 0
        clone_class_blockLevel_num = 0
        
        clone_class_fileLevel_segments_num = 0
        clone_class_blockLevel_segments_num = 0
        clone_class_segments_num = 0
        
        for cloneClass in cloneClassList:
            clone_class_segments_num += len(cloneClass)
            all_clone_class_segments_num += len(cloneClass)
            
            tokenBagA = tokenBagList[cloneClass[0][0]][cloneClass[0][1]][cloneClass[0][2]]
            if tokenBagA['granularity'] == 0:
                clone_class_fileLevel_num += 1
                clone_class_fileLevel_segments_num += len(cloneClass)
                all_clone_class_fileLevel_segments_num += len(cloneClass)
                
            else:
                clone_class_blockLevel_num += 1
                clone_class_blockLevel_segments_num += len(cloneClass)
                all_clone_class_blockLevel_segments_num += len(cloneClass)

        try:
            clone_class_segments_meanNum = clone_class_segments_num / clone_class_num
        except ZeroDivisionError:
            clone_class_segments_meanNum = 0
            
        try:
            clone_class_fileLevel_segments_meanNum = clone_class_fileLevel_segments_num / clone_class_fileLevel_num
        except ZeroDivisionError:
            clone_class_fileLevel_segments_meanNum = 0
        try:
            clone_class_blockLevel_segments_meanNum = clone_class_blockLevel_segments_num / clone_class_blockLevel_num
        except ZeroDivisionError:
            clone_class_blockLevel_segments_meanNum = 0
            
        all_clone_class_num += clone_class_num
        all_clone_class_fileLevel_num += clone_class_fileLevel_num
        all_clone_class_blockLevel_num += clone_class_blockLevel_num

        # Clone Class Nums and Clone Class Sizes with cross-project clones

        crossProjectClone_class_num = len(crossProjectCloneClass_list)
        crossProjectClone_class_fileLevel_num = 0
        crossProjectClone_class_blockLevel_num = 0
        
        crossProjectClone_class_fileLevel_segments_num = 0
        crossProjectClone_class_blockLevel_segments_num = 0
        crossProjectClone_class_segments_num = 0
        
        for cloneClass in crossProjectCloneClass_list:
            crossProjectClone_class_segments_num += len(cloneClass)
            all_crossProjectClone_class_segments_num += len(cloneClass)
            
            tokenBagA = tokenBagList[cloneClass[0][0]][cloneClass[0][1]][cloneClass[0][2]]
            if tokenBagA['granularity'] == 0:
                crossProjectClone_class_fileLevel_num += 1
                crossProjectClone_class_fileLevel_segments_num += len(cloneClass)
                all_crossProjectClone_class_fileLevel_segments_num += len(cloneClass)
                
            else:
                crossProjectClone_class_blockLevel_num += 1
                crossProjectClone_class_blockLevel_segments_num += len(cloneClass)
                all_crossProjectClone_class_blockLevel_segments_num += len(cloneClass)
        
        try:
            crossProjectClone_class_segments_meanNum = crossProjectClone_class_segments_num / crossProjectClone_class_num
        except ZeroDivisionError:
            crossProjectClone_class_segments_meanNum = 0
            
        try:
            crossProjectClone_class_fileLevel_segments_meanNum = crossProjectClone_class_fileLevel_segments_num / crossProjectClone_class_fileLevel_num
        except ZeroDivisionError:
            crossProjectClone_class_fileLevel_segments_meanNum = 0
        try:
            crossProjectClone_class_blockLevel_segments_meanNum = crossProjectClone_class_blockLevel_segments_num / crossProjectClone_class_blockLevel_num
        except ZeroDivisionError:
            crossProjectClone_class_blockLevel_segments_meanNum = 0      

        all_crossProjectClone_class_num += crossProjectClone_class_num
        all_crossProjectClone_class_fileLevel_num += crossProjectClone_class_fileLevel_num
        all_crossProjectClone_class_blockLevel_num += crossProjectClone_class_blockLevel_num
            
        
     
                
        ## Project with clones
        projectIdWithClone_set = set()
        projectIdWithClone_fileLevel_set = set()
        projectIdWithClone_blockLevel_set = set()
        
        ## Project with corss-project clones
        projectIdWithCrossProjectClone_set = set()
        projectIdWithCrossProjectClone_fileLevel_set = set()
        projectIdWithCrossProjectClone_blockLevel_set = set()
        
        ## Pair of cross-project clones
        crossProjectClone_num = 0
        crossProjectClone_fileLevel_num = 0
        crossProjectClone_blockLevel_num = 0
        
        ## Pair of intra-project clones
        intraProjectClone_num = 0
        intraProjectClone_fileLevel_num = 0
        intraProjectClone_blockLevel_num = 0
        
        
        ##  For Mean cross-project clone size
        crossProjectClone_meanSize = 0
        crossProjectClone_fileLevel_meanSize = 0
        crossProjectClone_blockLevel_meanSize = 0
        
        ## For Mean intra-project clone size
        intraProjectClone_meanSize = 0
        intraProjectClone_fileLevel_meanSize = 0
        intraProjectClone_blockLevel_meanSize = 0



        
        clone_meanSize = 0
        
        clone_fileLevel_num_kloc = 0
        clone_fileLevel_num_kloc = 0
        
        taskId = str(taskId)
        if taskId in projectSizeDict:
            clone_project_dict = projectSizeDict[taskId]
        else:
            print("3jnsdkjashdjhklsdfjsklaj")
            clone_project_dict = {
                "elements": {},
                "data": {}
            }
            
            for projectIndex in range(len(fileList)):
                if not projectIndex in clone_project_dict["elements"]:
                    projectPath = configObj['inputProject'][projectIndex]
                    projectName = os.path.basename(projectPath)
                    projectSize = get_code_line_count_project(projectPath) / 100000
                    clone_project_dict["elements"][projectIndex] = (projectSize, projectName)
            
            projectSizeDict[taskId] = clone_project_dict
            
            with open("./projectSizeDict.json", "w") as f:
                f.write(ujson.dumps(projectSizeDict))
        
        
        for clonePair in cloneList:
            projectIdWithClone_set.add(language + projectList[clonePair[0][0]])
            projectIdWithClone_set.add(language + projectList[clonePair[1][0]])    
            
            tokenBagA = tokenBagList[clonePair[0][0]][clonePair[0][1]][clonePair[0][2]]
            tokenBagB = tokenBagList[clonePair[1][0]][clonePair[1][1]][clonePair[1][2]]
            cloneSize = (tokenBagA["tokenNum"] + tokenBagB["tokenNum"]) / 2
        
            if clonePair[0][0] == clonePair[1][0]: # intra-project
                intraProjectClone_num += 1
                intraProjectClone_meanSize += cloneSize
                                
                if tokenBagA['granularity'] == 0 or tokenBagB['granularity'] == 0:
                    intraProjectClone_fileLevel_num += 1
                    intraProjectClone_fileLevel_meanSize += cloneSize
                
                    
                    projectIdWithClone_fileLevel_set.add(language + projectList[clonePair[0][0]])
                    projectIdWithClone_fileLevel_set.add(language + projectList[clonePair[1][0]])
                    
                else:
                    intraProjectClone_blockLevel_num += 1
                    intraProjectClone_blockLevel_meanSize += cloneSize
                    
                    projectIdWithClone_blockLevel_set.add(language + projectList[clonePair[0][0]])
                    projectIdWithClone_blockLevel_set.add(language + projectList[clonePair[1][0]])
                    
                    
            else: # cross-project
                projectIdWithCrossProjectClone_set.add(language + projectList[clonePair[0][0]])
                projectIdWithCrossProjectClone_set.add(language + projectList[clonePair[1][0]])
                crossProjectClone_num += 1
                crossProjectClone_meanSize += cloneSize
                
                if tokenBagA['granularity'] == 0 or tokenBagB['granularity'] == 0:
                    crossProjectClone_fileLevel_num += 1
                    crossProjectClone_fileLevel_meanSize += cloneSize
                    
                    projectIdWithCrossProjectClone_fileLevel_set.add(language + projectList[clonePair[0][0]])
                    projectIdWithCrossProjectClone_fileLevel_set.add(language + projectList[clonePair[1][0]])
                    projectIdWithClone_fileLevel_set.add(language + projectList[clonePair[0][0]])
                    projectIdWithClone_fileLevel_set.add(language + projectList[clonePair[1][0]])
                    
                else:
                    crossProjectClone_blockLevel_num += 1
                    crossProjectClone_blockLevel_meanSize += cloneSize
                    
                    projectIdWithCrossProjectClone_blockLevel_set.add(language + projectList[clonePair[0][0]])
                    projectIdWithCrossProjectClone_blockLevel_set.add(language + projectList[clonePair[1][0]])
                    projectIdWithClone_blockLevel_set.add(language + projectList[clonePair[0][0]])
                    projectIdWithClone_blockLevel_set.add(language + projectList[clonePair[1][0]])
                    
                
                
                
                    
                if not clonePair[0][0] in clone_project_dict["data"]:
                    clone_project_dict["data"][clonePair[0][0]] = {}
                    
                if not clonePair[1][0] in clone_project_dict["data"][clonePair[0][0]]:
                    clone_project_dict["data"][clonePair[0][0]][clonePair[1][0]] = 0
                else:
                    clone_project_dict["data"][clonePair[0][0]][clonePair[1][0]] += 1
            
            clone_meanSize += cloneSize
        
        # print(clone_project_dict)
        # drawProjectsGraph(clone_project_dict, str(taskId) + ".pdf")
        
        ## For Mean cross-project clone size
        all_crossProjectClone_meanSize += crossProjectClone_meanSize
        all_crossProjectClone_fileLevel_meanSize += crossProjectClone_fileLevel_meanSize
        all_crossProjectClone_blockLevel_meanSize += crossProjectClone_blockLevel_meanSize
        
        ## For Mean intra-project clone size
        all_intraProjectClone_meanSize += intraProjectClone_meanSize
        all_intraProjectClone_fileLevel_meanSize += intraProjectClone_fileLevel_meanSize
        all_intraProjectClone_blockLevel_meanSize += intraProjectClone_blockLevel_meanSize
        
        try:
            crossProjectClone_meanSize /= crossProjectClone_num
            crossProjectClone_blockLevel_meanSize /= crossProjectClone_blockLevel_num
            crossProjectClone_fileLevel_meanSize /= crossProjectClone_fileLevel_num
        except ZeroDivisionError:
            crossProjectClone_meanSize = 0
            crossProjectClone_fileLevel_meanSize = 0
            crossProjectClone_blockLevel_meanSize = 0
        
        try:
            intraProjectClone_meanSize /= intraProjectClone_num
            intraProjectClone_blockLevel_meanSize /= intraProjectClone_blockLevel_num
            intraProjectClone_fileLevel_meanSize /= intraProjectClone_fileLevel_num
            
        except ZeroDivisionError:
            intraProjectClone_meanSize = 0
            intraProjectClone_fileLevel_meanSize = 0
            intraProjectClone_blockLevel_meanSize = 0
            
        try:
            clone_meanSize /= len(cloneList)
        except ZeroDivisionError:
            clone_meanSize = 0
    
        project_loc_task = 0
        for projectElement in clone_project_dict["elements"]:
            project_loc_task += clone_project_dict["elements"][projectElement][0] * 10000
        
        try:
            crossProjectClone_fileLevel_num_kloc = crossProjectClone_fileLevel_num / (project_loc_task/100000)
            crossProjectClone_blockLevel_num_kloc = crossProjectClone_blockLevel_num / (project_loc_task/100000)
            crossProjectClone_num_kloc = crossProjectClone_num / (project_loc_task/100000)
        except ZeroDivisionError:
            crossProjectClone_fileLevel_num_kloc = 0
            crossProjectClone_blockLevel_num_kloc = 0
            crossProjectClone_num_kloc = 0


        
        # # print all the item in a single line csv format 
        # print("%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d" % (taskId, len(cloneList), len(fileList), len(projectIdWithClone_set), len(projectIdWithCrossProjectClone_set), rossProjectClone, num_intraProjectClone, num_crossProjectClone_blockLevel, num_crossProjectClone_fileLevel, size_crossProjectClone_meanSize, size_intraProjectClone_mean, clone_meanSize, clone_num_kloc, clone_fileLevel_num_kloc, clone_fileLevel_num_kloc, mean_segments_crossProjectClone_class,mean_segments_crossProjectClone_class_fileLevel,mean_segments_crossProjectClone_class_blockLevel,num_crossProjectClone_class_blockLevel,num_crossProjectClone_class_fileLevel,num_crossProjectClone_class))
        
        # print("taskId, crossProjectClone_FileLevel_Num, crossProjectClone_BlockLevel_Num, crossProjectClone_fileLevel_num_kloc, crossProjectClone_blockLevel_num_kloc, crossProjectClone_class_fileLevel_num, crossProjectClone_class_blockLevel_num, crossProjectClone_class_fileLevel_segments_meanNum, crossProjectClone_class_blockLevel_segments_meanNum")
        print("%s, %d, %d, %f, %f, %d, %d, %f, %f" % (taskId, crossProjectClone_fileLevel_num, crossProjectClone_blockLevel_num, crossProjectClone_fileLevel_num_kloc, crossProjectClone_blockLevel_num_kloc, crossProjectClone_class_fileLevel_num, crossProjectClone_class_blockLevel_num, crossProjectClone_class_fileLevel_segments_meanNum, crossProjectClone_class_blockLevel_segments_meanNum))

        
        
        # set_all_project = addItemsIntoSetFromSet(set_all_project, all_project_set)
        ## Project With Clones
        all_projectWithClone_set = addItemsIntoSetFromSet(all_projectWithClone_set, projectIdWithClone_set)
        all_projectWithClone_fileLevel_set = addItemsIntoSetFromSet(all_projectWithClone_fileLevel_set, projectIdWithClone_fileLevel_set)
        all_projectWithClone_blockLevel_set = addItemsIntoSetFromSet(all_projectWithClone_blockLevel_set, projectIdWithClone_blockLevel_set)
    

        
        ## Project With Cross Project Clones
        all_projectWithCrossProjectClone_set = addItemsIntoSetFromSet(all_projectWithCrossProjectClone_set, projectIdWithCrossProjectClone_set)
        all_projectWithCrossProjectClone_fileLevel_set = addItemsIntoSetFromSet(all_projectWithCrossProjectClone_fileLevel_set, projectIdWithCrossProjectClone_fileLevel_set)
        all_projectWithCrossProjectClone_blockLevel_set = addItemsIntoSetFromSet(all_projectWithCrossProjectClone_blockLevel_set, projectIdWithCrossProjectClone_blockLevel_set)
        
        
        
        ## Pair of Cross Project Clones
        all_crossProjectClone_num += crossProjectClone_num
        all_crossProjectClone_fileLevel_num += crossProjectClone_fileLevel_num
        all_crossProjectClone_blockLevel_num += crossProjectClone_blockLevel_num
        
        ## Pair of Intra Project Clones
        all_intraProject_clone_num += intraProjectClone_num
        all_intraProjectClone_fileLevel_num += intraProjectClone_fileLevel_num
        all_intraProjectClone_blockLevel_num += intraProjectClone_blockLevel_num
        

        

        


    # For Mean cross-project clone size    
    try:
        all_crossProjectClone_meanSize = all_crossProjectClone_meanSize / all_crossProjectClone_num
    except ZeroDivisionError:
        all_crossProjectClone_meanSize = 0
    try:
        all_crossProjectClone_fileLevel_meanSize = all_crossProjectClone_fileLevel_meanSize / all_crossProjectClone_fileLevel_num
    except ZeroDivisionError:
        all_crossProjectClone_fileLevel_meanSize = 0
    try:
        all_crossProjectClone_blockLevel_meanSize = all_crossProjectClone_blockLevel_meanSize / all_crossProjectClone_blockLevel_num
    except ZeroDivisionError:
        all_crossProjectClone_blockLevel_meanSize = 0
    
    # For Mean intra-project clone size
    try:
        all_intraProjectClone_meanSize = all_intraProjectClone_meanSize / all_intraProject_clone_num
    except ZeroDivisionError:
        all_intraProjectClone_meanSize = 0
    try:
        all_intraProjectClone_fileLevel_meanSize = all_intraProjectClone_fileLevel_meanSize / all_intraProjectClone_fileLevel_num
    except ZeroDivisionError:
        all_intraProjectClone_fileLevel_meanSize = 0
    try:
        all_intraProjectClone_blockLevel_meanSize = all_intraProjectClone_blockLevel_meanSize / all_intraProjectClone_blockLevel_num    
    except ZeroDivisionError:
        all_intraProjectClone_blockLevel_meanSize = 0

    # For Mean segments of clone classes 
    try:
        all_clone_class_segments_meanNum = all_clone_class_segments_num / all_clone_class_num
    except ZeroDivisionError:
        all_clone_class_segments_meanNum = 0
    
    try:
        all_clone_class_fileLevel_segments_meanNum = all_clone_class_fileLevel_segments_num / all_clone_class_fileLevel_num
    except ZeroDivisionError:   
        all_clone_class_fileLevel_segments_meanNum = 0
    
    try:    
        all_clone_class_blockLevel_segments_meanNum = all_clone_class_blockLevel_segments_num / all_clone_class_blockLevel_num
    except ZeroDivisionError:
        all_clone_class_blockLevel_segments_meanNum = 0

    # For Mean segments of clone classes contains cross-project clones
    try:
        all_crossProjectClone_class_segments_meanNum = all_crossProjectClone_class_segments_num / all_crossProjectClone_class_num
    except ZeroDivisionError:
        all_crossProjectClone_class_segments_meanNum = 0
    try:
        all_crossProjectClone_class_fileLevel_segments_meanNum = all_crossProjectClone_class_fileLevel_segments_num / all_crossProjectClone_class_fileLevel_num
    except ZeroDivisionError:
        all_crossProjectClone_class_fileLevel_segments_meanNum = 0
    try:
        all_crossProjectClone_class_blockLevel_segments_meanNum = all_crossProjectClone_class_blockLevel_segments_num / all_crossProjectClone_class_blockLevel_num       
    except ZeroDivisionError:
        all_crossProjectClone_class_blockLevel_segments_meanNum = 0

    print("##### all")
    print("All Projects: %d" % len(all_project_set))

    print("All Projects with Clone: %d" % len(all_projectWithClone_set))
    print("All Projects with Clone File Level: %d" % len(all_projectWithClone_fileLevel_set))
    print("All Projects with Clone Block Level: %d" % len(all_projectWithClone_blockLevel_set))

    print("All Projects with Cross Project Clone: %d" % len(all_projectWithCrossProjectClone_set))
    print("All Projects with Cross Project Clone File Level: %d" % len(all_projectWithCrossProjectClone_fileLevel_set))
    print("All Projects with Cross Project Clone Block Level: %d" % len(all_projectWithCrossProjectClone_blockLevel_set))

    print("All Cross Project Clone: %d" % all_crossProjectClone_num)
    print("All Cross Project Clone File Level: %d" %    all_crossProjectClone_fileLevel_num)
    print("All Cross Project Clone Block Level: %d" % all_crossProjectClone_blockLevel_num)

    print("All Intra Project Clone: %d" % all_intraProject_clone_num)
    print("All Intra Project Clone File Level: %d" % all_intraProjectClone_fileLevel_num)
    print("All Intra Project Clone Block Level: %d" % all_intraProjectClone_blockLevel_num)

    print("All Cross Project Clone Mean: %f" % all_crossProjectClone_meanSize)
    print("All Cross Project Clone Mean File Level: %f" % all_crossProjectClone_fileLevel_meanSize)
    print("All Cross Project Clone Mean Block Level: %f" %  all_crossProjectClone_blockLevel_meanSize)

    print("All Intra Project Clone Mean: %f" %  all_intraProjectClone_meanSize)
    print("All Intra Project Clone Mean File Level: %f" %   all_intraProjectClone_fileLevel_meanSize)
    print("All Intra Project Clone Mean Block Level: %f" %  all_intraProjectClone_blockLevel_meanSize)
    
    print("All Clone Class: %d" % all_clone_class_num)
    print("All Clone Class File Level: %d" % all_clone_class_fileLevel_num)
    print("All Clone Class Block Level: %d" % all_clone_class_blockLevel_num)

    print("All clone class contains cross-project clones: %d" % all_crossProjectClone_class_num)
    print("All clone class contains cross-project clones File Level: %d" %  all_crossProjectClone_class_fileLevel_num)
    print("All clone class contains cross-project clones Block Level: %d" % all_crossProjectClone_class_blockLevel_num)
    
    
    
    
    
    print("All Mean Segments of Clone Class: %f" % all_clone_class_segments_meanNum)
    print("All Mean Segments of Clone Class File Level: %f" % all_clone_class_fileLevel_segments_meanNum)
    print("All Mean Segments of Clone Class Block Level: %f" % all_clone_class_blockLevel_segments_meanNum)

    print("All Mean Segments of Cross Project Class: %f" % all_crossProjectClone_class_segments_meanNum)
    print("All Mean Segments of Cross Project Class File Level: %f" % all_crossProjectClone_class_fileLevel_segments_meanNum)
    print("All Mean Segments of Cross Project Class Block Level: %f" % all_crossProjectClone_class_blockLevel_segments_meanNum)    
    
    
    # projectSizeDict = ujson.loads(open("./projectSizeDict.json", "r").read())
   


        
        
    
    
