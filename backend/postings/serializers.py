from rest_framework import serializers
from postings.models import GeneralProductPostingGroup, GeneralBusinessPostingGroup

class GeneralProductPostingGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneralProductPostingGroup
        fields = ['system_id', 'code', 'description', 'created_at', 'updated_at']
        read_only_fields = ['system_id', 'created_at', 'updated_at']

class GeneralBusinessPostingGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneralBusinessPostingGroup
        fields = ['system_id', 'code', 'description', 'created_at', 'updated_at']
        read_only_fields = ['system_id', 'created_at', 'updated_at'] 