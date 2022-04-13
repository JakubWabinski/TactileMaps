def clear_selection(layer_name):
    arcpy.management.SelectLayerByAttribute(layer_name, "CLEAR_SELECTION")
        
def parameter_test(resource_name = arcpy.GetParameterAsText(1),
                         sort_a = 'FREQUENCY', 
                         sort_b = 'sort_b', 
                         sort_c = 'sort_c',  
                         min_distance = arcpy.GetParameterAsText(7) + ' Millimeters',
                         reference_scale = arcpy.GetParameterAsText(8),
                         symbol_size = arcpy.GetParameterAsText(9)):
    
    # ----- Script parameters -----
    try:
        arcpy.AddMessage('Running...' + resource_name)
        workspace = arcpy.env.workspace 
        workspace = arcpy.GetParameterAsText(0)

        arcpy.env.referenceScale = reference_scale
        search_distance = str(int(symbol_size) * arcpy.env.referenceScale / 1000) # TO BE PASSED AS FUNCTION ARGUMENTS
        displacement_value = str(float(search_distance)/2) # TO BE PASSED AS FUNCTION ARGUMENTS
        arcpy.AddMessage('search distance: ' + search_distance)
        arcpy.AddMessage('displacement value: ' + displacement_value)
        clear_selection(resource_name)

        # ----- First field for sorting ----- the number of features of specific type > those with the least occurences will be considered first in generalization    

        arcpy.analysis.Frequency(resource_name, 
                                 'ResourceCount', 
                                 'Type') # Create a table that will hold the frequency of particular resource types
        arcpy.management.JoinField(resource_name, 
                                   'Type', 
                                   'ResourceCount', 
                                   'Type', 
                                   'FREQUENCY')
        arcpy.SetParameterAsText(2, 'ResourceCount')

        # ----- Second field for sorting ----- the number of conflicting objects > those with the most conflicts will be considered first in generalization

        arcpy.management.AddField(resource_name, 
                                  sort_b, 
                                  'LONG') # add field to hold the number of proximate points (function's argument)
        with arcpy.da.UpdateCursor(resource_name, ('OBJECTID', sort_b)) as cursor: # iterate over feature class rows to update values    
            for row in cursor:
                selection = arcpy.management.SelectLayerByAttribute(resource_name, 
                                                                    'NEW_SELECTION', 
                                                                    'OBJECTID = {}'.format(row[0])) # select by attribute - iterate over every element in feature class
                arcpy.management.CopyFeatures(selection, 'temporary')
                arcpy.management.MakeFeatureLayer('temporary', 'temporary_layer')
                arcpy.management.ApplySymbologyFromLayer('temporary_layer', resource_name)
                arcpy.SetParameterAsText(3, 'temporary_layer')
                clear_selection(resource_name) # Clear the current selection - just in case
                arcpy.analysis.Erase(resource_name, 
                                     'temporary_layer', 
                                     'erase') # Perform Erase operation to get a subtraction of original layer and the selected feature
                arcpy.management.MakeFeatureLayer('erase', 'erase_layer')
                arcpy.management.ApplySymbologyFromLayer('erase_layer', resource_name)
                arcpy.SetParameterAsText(4, 'erase_layer')

                arcpy.cartography.DetectGraphicConflict('temporary_layer',
                                                       'erase_layer',
                                                       'conflict'
                                                       ) # Detect conflicting area between the selected feature (iterated) and the rest of the features in the original feature class
                conflicting_features = arcpy.management.SelectLayerByLocation(resource_name,
                                                      'INTERSECT',
                                                      'conflict',
                                                      search_distance = displacement_value + ' Meters' 
                                                      ) # Select objects that cause the conflict to determine their Mean Center
                row[1] = int(arcpy.management.GetCount(conflicting_features)[0]) # Get the number of featuers selected and assign the function's outpoot as a new column in the row
                cursor.updateRow(row) # update the current iteration row with the new value 

        # ----- Third field for sorting ----- the number of features in general within a specified threshold. Those with lower value will be considered first in generalization

        clear_selection(resource_name) # Clear selections just in case            
        arcpy.management.AddField(resource_name, 
                                  sort_c, 
                                  'LONG') # add field to hold the number of proximate points
        with arcpy.da.UpdateCursor(resource_name, ('OBJECTID', sort_c)) as cursor2: # other type of cursor for updating fields    
            for row in cursor2:
                selection2 = arcpy.SelectLayerByAttribute_management(resource_name, 
                                                                     'NEW_SELECTION', 
                                                                     'OBJECTID = {}'.format(row[0]))
                proximity_count2 = arcpy.management.GetCount(
                    arcpy.management.SelectLayerByLocation(selection2, 
                                                           'WITHIN_A_DISTANCE', 
                                                           resource_name, 
                                                           str(float(search_distance)*2)
                                                          )
                                                        )
                row[1] = int(proximity_count2.getOutput(0)) # convert 'Result' type object from .GetCount() into integer by using .getOutput()
                cursor2.updateRow(row) # update the current iteration row with the new value 

        # ----- sorted layer preparation -----

        clear_selection(resource_name) # Clear selections just in case
        resource_name_sorted = resource_name + '_sorted'
        arcpy.management.Sort(resource_name, 
                              resource_name_sorted, 
                              [[sort_a, 'ASCENDING'],[sort_b, 'DESCENDING'],  [sort_c, 'ASCENDING']]
                             )
        arcpy.management.MakeFeatureLayer(resource_name_sorted, resource_name_sorted)
        arcpy.management.ApplySymbologyFromLayer(resource_name_sorted, resource_name)
        arcpy.SetParameterAsText(5, resource_name_sorted)    

        # ------------------------------------------- Generalization -------------------------------------------
        
        arcpy.AddMessage('Start generalization')
        # Deleting the newly generated fields
        fclasses_list = [resource_name, resource_name_sorted]
        exclude_list = ['OBJECTID', 'Shape', 'Type', 'sort_b']

        for fclass in fclasses_list:
            for field in arcpy.ListFields(fclass):
                if field.name in exclude_list:
                    continue
                else: 
                    arcpy.management.DeleteField(fclass, 
                                                 field.name)

        resource_name_generalized = resource_name + '_generalized'
        arcpy.management.CreateFeatureclass(arcpy.env.workspace,  
                                            resource_name_generalized, 
                                            'POINT', 
                                            template = resource_name_sorted, 
                                            spatial_reference = arcpy.Describe(resource_name_sorted).name
                                           ) # Create a feature class to hold generalized outputs (mean_centers)
        arcpy.management.MakeFeatureLayer(resource_name_generalized, resource_name_generalized)
        arcpy.management.ApplySymbologyFromLayer(resource_name_generalized, resource_name)
        arcpy.SetParameterAsText(5, resource_name_generalized) 

        with arcpy.da.SearchCursor(resource_name_sorted, ('OBJECTID', 'sort_b')) as cursor:     
            for row in cursor:
                selection = arcpy.SelectLayerByAttribute_management(resource_name_sorted, 
                                                                    'NEW_SELECTION', 
                                                                    'OBJECTID = {}'.format(row[0])) # select by attribute - iterate over every element in feature class
                arcpy.management.CopyFeatures(selection, 'temporary')
                arcpy.management.MakeFeatureLayer('temporary', 'temporary_layer')
                arcpy.management.ApplySymbologyFromLayer('temporary_layer', resource_name)
                arcpy.SetParameterAsText(3, 'temporary_layer')
                clear_selection(resource_name_sorted) # Clear the current selection - just in case

                arcpy.analysis.Erase(resource_name_sorted, 
                                     'temporary_layer', 
                                     'erase') # Perform Erase operation to get a subtraction of original layer and the selected feature
                arcpy.management.MakeFeatureLayer('erase', 'erase_layer')
                arcpy.management.ApplySymbologyFromLayer('erase_layer', resource_name)
                arcpy.SetParameterAsText(4, 'erase_layer')

                arcpy.cartography.DetectGraphicConflict('temporary_layer',
                                                       'erase_layer',
                                                       'conflict'
                                                       ) # Detect conflicting area between the selected feature (iterated) and the rest of the features in the original feature class

                conflicting_features = arcpy.management.SelectLayerByLocation(resource_name_sorted,
                                                                              'INTERSECT',
                                                                              'conflict',
                                                                              search_distance = displacement_value + ' Meters' 
                                                                             ) # Select objects that cause the conflict to determine their Mean Center
                matchcount = int(arcpy.GetCount_management(conflicting_features)[0]) # Get the number of featuers selected

                # Control measures:
                arcpy.AddMessage('row number: ' + str(row[0]))
                arcpy.AddMessage('matched objects: ' + str(matchcount)) 
                arcpy.AddMessage('sort_b value: ' + str(row[1]) +'\n' + str('-'*10))
                # ----------------
                if matchcount > 2:
                    arcpy.management.Append('temporary',
                                           resource_name_generalized
                                           )
                    arcpy.management.DeleteFeatures(conflicting_features) # Delete the original selected features
                if matchcount == 2:
                    MeanCenterTemp = arcpy.stats.MeanCenter(conflicting_features, 
                                                            'MeanCenter'
                                                           )
                    arcpy.management.DeleteField('MeanCenter', 
                                                 ['XCoord','YCoord','ZCoord']
                                                ) # Delete fields breaking the schema # 
                    arcpy.management.AddField('MeanCenter', 
                                              'Type',
                                             'TEXT'
                                             )
                    arcpy.management.AddField('MeanCenter', 
                                              'sort_b',
                                             'LONG'
                                             )
                    with arcpy.da.UpdateCursor('MeanCenter', 'Type') as cursor1:
                        with arcpy.da.SearchCursor('temporary', 'Type') as cursor2:
                            for row1, row2 in zip(cursor1,cursor2):
                                row1[0]=row2[0]
                                cursor1.updateRow(row1)
                    # -------------------------------- 
                    arcpy.management.Append(MeanCenterTemp, 
                                            resource_name_generalized
                                           ) # Append generalization results to the newly created feature class
                    arcpy.management.Delete(MeanCenterTemp) # Delete the temporary MeanCenter with unwanted symbology
                    arcpy.management.DeleteFeatures(conflicting_features) # Delete the original selected features
                    clear_selection(resource_name_sorted) # Clear the current selection - just in case                                       
                else: 
                    arcpy.management.Append('temporary_layer', 
                                            resource_name_generalized
                                           ) # Append generalization results to the newly created feature class 

        arcpy.management.DeleteIdentical(resource_name_generalized, 'Shape')
        arcpy.cartography.DisperseMarkers(resource_name_generalized, min_distance, 'EXPANDED') # get the layer name by using string object 

        arcpy.AddMessage('SUCCESS!')

    finally:
         arcpy.management.Delete(['ResourceCount', 'conflict', 'erase', 'temporary']) #, arcpy.Describe(resource_name_sorted).name
         arcpy.management.DeleteField(resource_name, sort_b)
         arcpy.management.DeleteField(resource_name_generalized, sort_b)
         arcpy.management.ClearWorkspaceCache() # For optimization

parameter_test()
