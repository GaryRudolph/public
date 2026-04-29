# Docker convenience commands. Defined as functions so the inner `(docker ...)`
# expansion is deferred to call time (and we don't error at startup if the
# daemon isn't running).

if command -q docker
    function docker_stop_all --description 'Stop all docker containers'
        docker stop (docker ps -a -q)
    end

    function docker_rm_all --description 'Remove all docker containers'
        docker rm (docker ps -a -q)
    end

    function docker_rmi_all --description 'Remove all docker images'
        docker rmi (docker images -q)
    end

    function docker_rmi_dangling --description 'Remove dangling docker images'
        docker rmi (docker images -q -f dangling=true)
    end
end
